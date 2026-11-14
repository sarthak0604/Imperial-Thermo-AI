"""Local and Cloud Run workload entry point."""

import os


def main() -> None:
    """Run the application on the laptop or in Cloud Run."""
    # Replace this smoke test with the application entry point.
    import torch

    execution = os.environ.get("CLOUD_RUN_EXECUTION")
    target = f"Cloud Run ({execution})" if execution else "local"
    result = (torch.tensor([1, 2, 3], device="cpu") ** 2).sum().item()
    print(f"Imperial Thermo AI smoke test on {target}: PyTorch {torch.__version__}, result={result}")
    print('Hello')

if __name__ == "__main__":
    main()
