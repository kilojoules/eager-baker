"""runpod_deploy.py — deploy / inspect / terminate a vLLM pod for any HF model.

Usage:
  python3 runpod_deploy.py up   <tag> <model_id> <gpu_name> [max_len] [extra_vllm_args]
  python3 runpod_deploy.py status <tag>
  python3 runpod_deploy.py down  <tag>
Records pod info to results/runpod_<tag>.json. Only one pod runs at a time if you
`down` the previous tag first (keeps cost ~1 GPU).
"""
import os, sys, json, runpod

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.normpath(os.path.join(HERE, "..", "results"))
runpod.api_key = open(os.path.expanduser("~/.run.pod")).read().strip()


def info_path(tag):
    return os.path.join(RES, f"runpod_{tag}.json")


def up(tag, model_id, gpu, max_len="16384", extra=""):
    docker_args = (f"--model {model_id} --served-model-name {model_id} "
                   f"--port 8000 --max-model-len {max_len} "
                   f"--gpu-memory-utilization 0.92 --max-num-seqs 16 {extra}").strip()
    pod = runpod.create_pod(
        name=f"scopecal-{tag}",
        image_name="vllm/vllm-openai:latest",
        gpu_type_id=gpu,
        cloud_type="COMMUNITY",
        gpu_count=1,
        container_disk_in_gb=120,
        min_vcpu_count=8,
        min_memory_in_gb=48,
        ports="8000/http",
        docker_args=docker_args,
        env={"HF_HUB_ENABLE_HF_TRANSFER": "1"},
    )
    pod["_model_id"] = model_id
    pod["_base_url"] = f"https://{pod['id']}-8000.proxy.runpod.net/v1"
    json.dump(pod, open(info_path(tag), "w"), indent=2)
    print("created", tag, "pod", pod["id"])
    print("base_url:", pod["_base_url"])


def status(tag):
    info = json.load(open(info_path(tag)))
    pod = runpod.get_pod(info["id"])
    print(f"{tag} pod {info['id']} desired={pod.get('desiredStatus')} "
          f"runtime={'up' if pod.get('runtime') else 'pending'}")
    print("base_url:", info["_base_url"])


def down(tag):
    info = json.load(open(info_path(tag)))
    runpod.terminate_pod(info["id"])
    print("terminated", tag, info["id"])


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "up":
        up(*sys.argv[2:])
    elif cmd == "status":
        status(sys.argv[2])
    elif cmd == "down":
        down(sys.argv[2])
