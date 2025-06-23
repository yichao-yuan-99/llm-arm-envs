import json
from vllm import LLM, SamplingParams

# Sample prompts.
prompts = [
    "Write a hello world program in C",
    "Write a hello world program in Java",
    "Write a hello world program in Rust",
]

# Create a sampling params object.
sampling_params = SamplingParams(temperature=0.8, top_p=0.95, max_tokens=256)

# Create an LLM.
llm = LLM(model="Qwen/Qwen2.5-0.5B-Instruct", dtype="bfloat16")

# Generate texts from the prompts. The output is a list of RequestOutput objects
# that contain the prompt, generated text, and other information.
outputs = llm.generate(prompts, sampling_params)

# Print the outputs.
for output in outputs:
    prompt = output.prompt
    generated_text = output.outputs[0].text
    result = {
        "Prompt": prompt,
        "Generated text": generated_text
    }
    print(json.dumps(result, indent=4))