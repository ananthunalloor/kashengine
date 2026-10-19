"""Superuser-only configuration of encrypted daily backups."""

from pathlib import Path
from typing import ClassVar
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django import forms

from apps.siteconfig import crypto

from . import backup_automation, backups
from .forms import CHECKBOX, INPUT
from .models import BackupConfiguration


class BackupConfigurationForm(forms.ModelForm):
    """Keep stored credentials encrypted, and never render them back to the browser."""

    access_key = forms.CharField(
        required=False,
        help_text="Leave blank to keep the saved access key.",
        widget=forms.PasswordInput(attrs={"class": INPUT, "autocomplete": "new-password"}),
    )
    secret_key = forms.CharField(
        required=False,
        help_text="Leave blank to keep the saved secret key.",
        widget=forms.PasswordInput(attrs={"class": INPUT, "autocomplete": "new-password"}),
    )
    clear_credentials = forms.BooleanField(required=False, label="Clear saved S3 credentials")

    class Meta:
        model = BackupConfiguration
        fields = (
            "enabled",
            "backup_time",
            "timezone",
            "destination",
            "local_directory",
            "bucket",
            "prefix",
            "endpoint_url",
            "region",
        )
        widgets: ClassVar[dict] = {
            "enabled": forms.CheckboxInput(attrs={"class": CHECKBOX}),
            "backup_time": forms.TimeInput(format="%H:%M", attrs={"type": "time", "class": INPUT}),
            "destination": forms.Select(attrs={"class": INPUT}),
            **{
                name: forms.TextInput(attrs={"class": INPUT, "autocomplete": "off"})
                for name in (
                    "timezone",
                    "local_directory",
                    "bucket",
                    "prefix",
                    "endpoint_url",
                    "region",
                )
            },
        }

    def clean_timezone(self) -> str:
        """Accept only real IANA time zones.

        Returns:
            The validated IANA time zone name.

        Raises:
            forms.ValidationError: The name is not a supported time zone.
        """
        value = self.cleaned_data["timezone"]
        try:
            ZoneInfo(value)
        except (ValueError, ZoneInfoNotFoundError) as exc:
            raise forms.ValidationError("Enter an IANA time zone, such as Asia/Kolkata.") from exc
        return value

    def clean_backup_time(self):
        """Require a daily time with minute resolution.

        Returns:
            The selected local clock time.

        Raises:
            forms.ValidationError: Seconds or microseconds were supplied.
        """
        value = self.cleaned_data["backup_time"]
        if value.second or value.microsecond:
            raise forms.ValidationError("Choose a time with hours and minutes only.")
        return value

    def clean_endpoint_url(self) -> str:
        """Validate HTTPS storage or a bundled Silo endpoint.

        Returns:
            A validated endpoint URL, or an empty string for Amazon S3.

        Raises:
            forms.ValidationError: The URL is insecure or contains credentials/query data.
        """
        value = self.cleaned_data["endpoint_url"]
        try:
            backup_automation.validate_s3_endpoint(value)
        except backups.BackupError as exc:
            raise forms.ValidationError(str(exc)) from exc
        return value

    def clean(self) -> dict:
        """Require a usable key and destination before enabling the scheduler.

        Returns:
            Cleaned configuration values, with field errors recorded when invalid.
        """
        data = super().clean() or {}
        if not data.get("enabled"):
            return data
        try:
            backups.backup_cipher()
        except backups.BackupError as exc:
            self.add_error("enabled", str(exc))
        if data.get("destination") == BackupConfiguration.Destination.LOCAL:
            path = Path(data.get("local_directory", ""))
            if not path.is_absolute():
                self.add_error("local_directory", "Enter an absolute path mounted in the worker.")
        elif data.get("destination") == BackupConfiguration.Destination.S3:
            if not data.get("bucket"):
                self.add_error("bucket", "An S3 bucket is required.")
            for field, encrypted in (
                ("access_key", self.instance.access_key_encrypted),
                ("secret_key", self.instance.secret_key_encrypted),
            ):
                saved = "" if data.get("clear_credentials") else encrypted
                if not data.get(field) and (not saved or not crypto.decrypt(saved)):
                    self.add_error(field, "Enter S3 credentials before enabling backups.")
        return data

    def save_for(self, actor) -> BackupConfiguration:
        """Encrypt new credentials and save the config and Beat entry atomically.

        Args:
            actor: The active superuser authorizing future backups.

        Returns:
            The persisted singleton configuration.
        """
        config = super().save(commit=False)
        for field, attribute in (
            ("access_key", "access_key_encrypted"),
            ("secret_key", "secret_key_encrypted"),
        ):
            if self.cleaned_data.get("clear_credentials"):
                setattr(config, attribute, "")
            if value := self.cleaned_data.get(field):
                setattr(config, attribute, crypto.encrypt(value))
        backup_automation.save_configuration(config, actor)
        return config
