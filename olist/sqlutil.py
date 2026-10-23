"""Small helper for running .sql files statement by statement."""


def split_statements(sql: str) -> list[str]:
    """Split a SQL script into statements.

    Strips `--` comments and splits on `;`. Good enough for the files in this repo,
    which contain no semicolons or `--` inside string literals.
    """
    lines = [line.split("--", 1)[0] for line in sql.splitlines()]
    return [part.strip() for part in "\n".join(lines).split(";") if part.strip()]
