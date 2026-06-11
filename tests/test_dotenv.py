# cli.load_dotenv — .env 파일의 환경변수 주입 (네트워크 없음).

from srm.cli import load_dotenv


def test_load_dotenv_sets_variables(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text(
        "# 주석은 무시\n"
        "\n"
        "FRED_API_KEY=abc123\n"
        'QUOTED="with quotes"\n'
        "등호 없는 잘못된 줄은 무시된다\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    monkeypatch.delenv("QUOTED", raising=False)

    load_dotenv(str(env))

    import os

    assert os.environ["FRED_API_KEY"] == "abc123"
    assert os.environ["QUOTED"] == "with quotes"


def test_load_dotenv_does_not_override_existing(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("FRED_API_KEY=from_file\n", encoding="utf-8")
    monkeypatch.setenv("FRED_API_KEY", "from_shell")

    load_dotenv(str(env))

    import os

    assert os.environ["FRED_API_KEY"] == "from_shell"


def test_load_dotenv_missing_file_is_noop(tmp_path):
    # 파일이 없어도 예외 없이 조용히 넘어간다(degrade).
    load_dotenv(str(tmp_path / "no_such.env"))
