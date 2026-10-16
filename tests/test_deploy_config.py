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
        "DOCS_ALLOWED_IPS",
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
        "reverse_proxy docs:8080",
        "{$SITE_ADDRESS}",
    ):
        assert needle in text, f"The Caddyfile is missing: {needle}"


def test_caddyfile_limits_the_ops_pages_like_the_admin_site():
    text = (ROOT / "deploy" / "caddy" / "Caddyfile").read_text()
    assert "path /admin /admin/* /ops /ops/*" in text
    assert "not remote_ip {$ADMIN_ALLOWED_IPS" in text


def site_block_lines() -> list[str]:
    """Return the lines inside the `{$SITE_ADDRESS} { ... }` block of the Caddyfile."""
    lines = (ROOT / "deploy" / "caddy" / "Caddyfile").read_text().splitlines()
    start = lines.index("{$SITE_ADDRESS} {")
    end = next(i for i in range(start + 1, len(lines)) if lines[i] == "}")
    return lines[start + 1 : end]


def test_caddy_routes_are_inside_handle_blocks():
    """A `respond` or `reverse_proxy` outside `handle` runs after a catch-all `handle`.

    Caddy sorts the `handle` directive before `respond`. A catch-all `handle` then ends the
    request first, and the rule outside never runs. The admin IP limit was dead code for that
    reason once. Keep every routing directive inside a `handle` block.
    """
    depth = 0
    for line in site_block_lines():
        text = line.strip()
        if depth == 0 and text.startswith(("respond ", "reverse_proxy ")):
            pytest.fail(f"Routing directive outside a handle block: {text}")
        depth += text.count("{") - text.count("}") if not text.startswith("#") else 0


def test_caddy_checks_the_admin_ip_limit_before_the_catch_all():
    text = "\n".join(site_block_lines())
    assert text.index("handle @admin_denied") < text.index("handle @docs_path")
    assert text.index("handle @docs_path") < text.index("\thandle {\n")


def test_docs_content_security_policy_is_not_set_by_caddy():
    """The docs site sets its own policy with script hashes. A second policy would add to it."""
    text = (ROOT / "deploy" / "caddy" / "Caddyfile").read_text()
    docs_header = text[text.index("header @docs_path") : text.index("@application_path")]
    assert "Content-Security-Policy" not in docs_header
    assert "{$CSP_HEADER" not in docs_header


@pytest.mark.skipif(shutil.which("caddy") is None, reason="The caddy binary is not installed.")
def test_caddyfile_adapts_and_runs_the_admin_limit_first(monkeypatch):
    """Adapt the Caddyfile with the real Caddy and check the order of the routes."""
    monkeypatch.setenv("SITE_ADDRESS", "kash.example.com")
    monkeypatch.setenv("ACME_EMAIL", "a@example.com")
    caddy = shutil.which("caddy")
    assert caddy is not None
    result = subprocess.run(  # noqa: S603
        [caddy, "adapt", "--config", str(ROOT / "deploy" / "caddy" / "Caddyfile")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    config, _end = json.JSONDecoder().raw_decode(result.stdout)
    site = next(
        route
        for server in config["apps"]["http"]["servers"].values()
        for route in server["routes"]
        if route.get("match", [{}])[0].get("host") == ["kash.example.com"]
    )
    routes = site["handle"][0]["routes"]
    handled = [
        route
        for route in routes
        if route["handle"] and route["handle"][0]["handler"] in {"subroute", "static_response"}
    ]
    texts = [json.dumps(route) for route in handled]
    admin = next(i for i, text in enumerate(texts) if "/ops/*" in text)
    catch_all = next(i for i, route in enumerate(handled) if "match" not in route)
    assert admin < catch_all


def test_docs_service_is_private_and_read_only(prod):
    docs = prod["services"]["docs"]
    assert docs["networks"] == ["proxy"]
    assert docs["read_only"] is True
    assert "ports" not in docs
    assert "env_file" not in docs


def test_docs_nginx_serves_under_the_public_path():
    text = (ROOT / "docs" / "nginx.conf").read_text()
    assert "location /docs/" in text
    assert "absolute_redirect off" in text
    assert "unsafe-inline" not in text


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
        (tmp_path / env_file).write_text(
            "MINIO_ROOT_USER=test-minio-user\nMINIO_ROOT_PASSWORD=test-minio-password\n"
        )
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


def test_minio_is_private_persistent_and_initialized_in_prod(prod_config):
    services = prod_config["services"]
    storage = services["minio"]
    assert set(storage["networks"]) == {"backend"}
    assert storage["read_only"] is True
    assert not storage.get("ports")
    assert any(
        volume["source"] == "minio_data" and volume["target"] == "/data"
        for volume in storage["volumes"]
    )
    initializer = services["minio-init"]
    assert set(initializer["networks"]) == {"backend"}
    assert initializer["restart"] == "no"
    assert initializer["read_only"] is True
    assert initializer["depends_on"]["minio"]["condition"] == "service_healthy"
    assert not initializer.get("ports")
    assert storage["image"] == initializer["image"]
    assert ":RELEASE." in storage["image"]


def test_minio_dev_ports_are_loopback_only(dev_config):
    ports = dev_config["services"]["minio"]["ports"]
    assert {port["published"] for port in ports} == {"9000", "9001"}
    assert {port["host_ip"] for port in ports} == {"127.0.0.1"}


@pytest.mark.parametrize(
    ("config_name", "env_file"),
    [("dev", ".env.dev"), ("prod", ".env.prod")],
)
def test_minio_uses_the_application_environment_file(request, config_name, env_file):
    config = request.getfixturevalue(config_name)
    for service in ("minio", "minio-init"):
        assert config["services"][service]["env_file"] == env_file


@pytest.mark.parametrize("config_name", ["dev_config", "prod_config"])
def test_minio_receives_shared_environment_credentials(request, config_name):
    config = request.getfixturevalue(config_name)
    for service in ("minio", "minio-init"):
        environment = config["services"][service]["environment"]
        assert environment["MINIO_ROOT_USER"] == "test-minio-user"
        assert environment["MINIO_ROOT_PASSWORD"] == "test-minio-password"


def test_minio_initialization_remains_idempotent():
    script = (ROOT / "deploy" / "minio" / "initialize.sh").read_text()
    assert "set -eu" in script
    assert "mb --ignore-existing storage/kashengine-backups" in script
    assert "mb --ignore-existing storage/kashengine-reports" in script
