"""Check that the Docker files keep the services private and Caddy is the only way in."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parent.parent
PUBLIC_PORTS = {"80:80", "443:443", "443:443/udp"}


def load(name: str) -> dict:
    return yaml.safe_load((ROOT / name).read_text())


@pytest.fixture(scope="module")
def base() -> dict:
    return load("docker-compose.yml")


@pytest.fixture(scope="module")
def dev() -> dict:
    return load("docker-compose.override.yml")


@pytest.fixture(scope="module")
def prod() -> dict:
    return load("docker-compose.prod.yml")


def test_base_file_publishes_no_port(base):
    for name, service in base["services"].items():
        assert "ports" not in service, f"{name} publishes a port in the base file"


def test_dev_ports_are_bound_to_loopback(dev):
    for name, service in dev["services"].items():
        for port in service.get("ports", []):
            assert port.startswith("127.0.0.1:"), f"{name} publishes {port} to all interfaces"


def test_only_caddy_publishes_ports_in_prod(prod):
    for name, service in prod["services"].items():
        if name == "caddy":
            assert set(service["ports"]) == PUBLIC_PORTS
        else:
            assert "ports" not in service, f"{name} publishes a port in prod"


def test_backend_and_proxy_networks_have_no_internet(prod):
    assert prod["networks"]["backend"]["internal"] is True
    assert prod["networks"]["proxy"]["internal"] is True


@pytest.mark.parametrize("name", ["web", "worker", "beat", "db", "redis", "ollama"])
def test_services_are_not_on_the_edge_network(prod, name):
    assert "edge" not in prod["services"][name]["networks"]


@pytest.mark.parametrize("name", ["db", "redis"])
def test_data_stores_are_on_the_backend_network_only(prod, name):
    assert prod["services"][name]["networks"] == ["backend"]


def test_web_has_no_route_to_the_internet(prod):
    assert "egress" not in prod["services"]["web"]["networks"]


def test_caddy_gets_no_app_secrets(prod):
    caddy = prod["services"]["caddy"]
    assert "env_file" not in caddy
    assert set(caddy["environment"]) == {
        "SITE_ADDRESS",
        "ACME_EMAIL",
        "ADMIN_ALLOWED_IPS",
        "CSP_HEADER",
    }


def test_caddyfile_has_the_security_settings():
    text = (ROOT / "deploy" / "caddy" / "Caddyfile").read_text()
    for needle in (
        "admin off",
        "request_body",
        "max_size",
        "header_down -Server",
        "Permissions-Policy",
        "frame-ancestors 'none'",
        "object-src 'none'",
        "reverse_proxy web:8000",
        "{$SITE_ADDRESS}",
    ):
        assert needle in text, f"The Caddyfile is missing: {needle}"


# The tests below read the merged files, as Docker Compose sees them. They need the docker CLI
# (no Docker daemon). They are skipped when it is missing.


def merged_config(tmp_path: Path, *names: str) -> dict:
    """Return the config that `docker compose config` makes from the given compose files."""
    docker = shutil.which("docker")
    if docker is None:
        pytest.skip("The docker CLI is not installed.")
    for name in (*names, "docker-compose.yml"):
        shutil.copy(ROOT / name, tmp_path / name)
    (tmp_path / "deploy").symlink_to(ROOT / "deploy")
    for env_file in (".env.dev", ".env.prod"):
        (tmp_path / env_file).touch()
    (tmp_path / "test.env").write_text("SITE_ADDRESS=kash.example.com\nACME_EMAIL=a@example.com\n")
    command = [docker, "compose", "--env-file", "test.env"]
    for name in dict.fromkeys(("docker-compose.yml", *names)):
        command += ["-f", name]
    command += ["config", "--format", "json"]
    result = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, check=False)  # noqa: S603
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.fixture
def prod_config(tmp_path) -> dict:
    return merged_config(tmp_path, "docker-compose.prod.yml")


@pytest.fixture
def dev_config(tmp_path) -> dict:
    return merged_config(tmp_path, "docker-compose.override.yml")


def test_every_prod_service_drops_capabilities(prod_config):
    for name, service in prod_config["services"].items():
        assert service["cap_drop"] == ["ALL"], f"{name} keeps capabilities"
        assert "no-new-privileges:true" in service["security_opt"], f"{name} can gain privileges"


def test_caddy_is_the_only_public_service_in_prod(prod_config):
    published = {
        name: [(port.get("host_ip"), port["published"]) for port in service.get("ports", [])]
        for name, service in prod_config["services"].items()
    }
    assert {name for name, ports in published.items() if ports} == {"caddy"}


def test_caddy_is_available_in_dev_on_loopback(dev_config):
    caddy = dev_config["services"]["caddy"]
    assert {port["published"] for port in caddy["ports"]} == {"80", "443"}
    assert {port["host_ip"] for port in caddy["ports"]} == {"127.0.0.1"}
    assert caddy["environment"]["SITE_ADDRESS"] == "localhost"
    assert caddy["cap_drop"] == ["ALL"]
    assert caddy["read_only"] is True


def test_dev_has_no_port_on_all_interfaces(dev_config):
    for name, service in dev_config["services"].items():
        for port in service.get("ports", []):
            assert port["host_ip"] == "127.0.0.1", f"{name} publishes {port['published']} publicly"
