from pathlib import Path
from compute_mixture_transport_and_lewis_number import run_from_json_file

# Always resolve the JSON file in the exact same folder as this script
json_path = Path(__file__).resolve().parent / "test_thm02_llm_input.json"

response = run_from_json_file(json_path)
print(response["dimensionless_numbers"])