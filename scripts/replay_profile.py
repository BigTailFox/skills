"""Check the operator's nonsecret routing and read grants against a frozen case."""
from pathlib import Path

from replay_git import ReplayError, safe_relative
from replay_workspace import project_instructions, scoped_paths, skills_path, tool_paths


def strings(value):
    return isinstance(value, list) and all(isinstance(v, str) and v.strip() for v in value)


def read_grant(config, names):
    grants = config["read_paths"]
    for name in names:
        if not any(p == "." or name == p or name.startswith(p + "/") for p in grants):
            raise ReplayError(f"runner read_paths do not grant the required input: {name}")


def profile(config, private, receipt):
    required = {"schema", "host", "default_effort", "roles", "destinations", "read_paths", "test_tools", "settings"}
    if (not required <= config.keys() or type(config["schema"]) is not int or config["schema"] != 1 or
            not all(strings(config[k]) for k in ("destinations", "read_paths", "test_tools")) or
            not isinstance(config["roles"], dict) or not isinstance(config["settings"], dict) or
            not isinstance(config["default_effort"], str) or not config["default_effort"].strip()):
        raise ReplayError("invalid runner configuration v1")
    if receipt["incompatibilities"]:
        raise ReplayError("; ".join(receipt["incompatibilities"]))
    if receipt["host"] != config["host"]:
        raise ReplayError("runner host differs from the recorded host")
    roles = {}
    destinations = set(config["destinations"])
    routing = config["settings"].get("role_destinations", {})
    if not isinstance(routing, dict) or not all(isinstance(v, str) for v in routing.values()):
        raise ReplayError("invalid role destinations")
    for key, historical in receipt["roles"].items():
        setting = config["roles"].get(key)
        model = historical["model"]
        if (not model or model.startswith("manual:") or not isinstance(setting, dict) or
                setting.get("model") != model or "effort" not in setting):
            raise ReplayError(f"{key} model missing or incompatible")
        effort = setting["effort"]
        if effort is not None and (not isinstance(effort, str) or not effort.strip()):
            raise ReplayError(f"invalid {key} effort")
        provider = routing.get(key)
        if provider is None:
            if "/" in model:
                provider = model.split("/", 1)[0]
            elif len(destinations) == 1:
                provider = next(iter(destinations))
        if provider not in destinations:
            raise ReplayError(f"{key} destination missing, ambiguous or ungranted")
        roles[key] = dict(model=model, effort=historical["effort"] or effort or config["default_effort"])
    if "parent" not in roles or len(roles) < 2:
        raise ReplayError("historical role unavailable")
    for grant in config["read_paths"]:
        if grant != ".":
            safe_relative(grant)
    root = private / "input"
    task = receipt["task"]
    required_paths = set(receipt["fixtures"]) | scoped_paths(root, task)
    required_paths.update(p.relative_to(root).as_posix() for p in project_instructions(root, task))
    required_paths.update(str(Path(p)) for p in tool_paths(root, task))
    prefix = skills_path(receipt["host"])
    for arm in ("recorded", "candidate"):
        suite = private / "suites" / arm
        required_paths.update(prefix + "/" + p.relative_to(suite).as_posix() for p in suite.rglob("*") if p.is_file())
    read_grant(config, sorted(required_paths))
    return roles
