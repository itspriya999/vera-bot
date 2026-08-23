from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8080
    team_name: str = "Vera Challenge Team"
    team_members: str = "Participant"
    model: str = "vera-rule-engine-v1"
    approach: str = (
        "Context-grounded signal ranking with category-specific message strategies"
    )
    version: str = "1.0.0"
    contact_email: str = "team@example.com"
    log_level: str = "INFO"

    @property
    def team_members_list(self) -> list[str]:
        return [m.strip() for m in self.team_members.split(",") if m.strip()]


settings = Settings()
