"""Run the same request workflow locally and in the cloud container."""


def main() -> int:
    from request_planner.service import main as run_workflow

    return run_workflow()

if __name__ == "__main__":
    raise SystemExit(main())
