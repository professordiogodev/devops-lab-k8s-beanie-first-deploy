#!/usr/bin/env python3
import json, os, re, socket, subprocess, sys, time, urllib.request, urllib.error
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(ROOT)
NS = "beanie"
passed = failed = 0
IMG = open(".image").read().strip()
SERVICES = {"menu": 8001, "payments": 8003, "notifications": 8004, "orders": 8002, "gateway": 8000}


def check(desc, ok, hint=""):
    global passed, failed
    if ok:
        passed += 1; print("PASS  " + desc)
    else:
        failed += 1; print("FAIL  " + desc + (("   -> " + hint) if hint else ""))


def k(*a, timeout=120):
    r = subprocess.run(("kubectl",) + a, capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout, r.stderr


def kj(*a):
    rc, out, _ = k(*a, "-o", "json")
    try:
        return json.loads(out) if rc == 0 else None
    except Exception:
        return None


def finish():
    print()
    print(("ALL CHECKS PASSED (%d/%d)" % (passed, passed)) if failed == 0 else ("%d check(s) failed, %d passed" % (failed, passed)))
    sys.exit(1 if failed else 0)


def wait_for(fn, secs, step=3):
    end = time.time() + secs
    while time.time() < end:
        if fn():
            return True
        time.sleep(step)
    return False


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def http(url, data=None, timeout=8):
    try:
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"} if data else {})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
    except Exception:
        return 0, ""


print("kubectl context: " + k("config", "current-context")[1].strip())
print("== Your manifests, as the cluster sees them ==")
check("the namespace %s exists" % NS, k("get", "namespace", NS)[0] == 0, "kubectl apply -f k8s/")
deps = {d["metadata"]["name"]: d for d in (kj("get", "deployments", "-n", NS) or {}).get("items", [])}
check("five Deployments: gateway, menu, orders, payments, notifications", set(deps) == set(SERVICES), "found: %s" % ", ".join(sorted(deps)))
if set(deps) != set(SERVICES):
    finish()


def c0(n):
    return deps[n]["spec"]["template"]["spec"]["containers"][0]


check("every container uses the image from .image (%s)" % IMG, all(c0(n)["image"] == IMG for n in deps))
check("every Deployment starts the right service (args: [<service>])", all((c0(n).get("args") or [])[-1:] == [n] for n in deps))
check("liveness probes call /healthz and readiness probes call /readyz, on the right port", all(
    c0(n).get("livenessProbe", {}).get("httpGet", {}).get("path") == "/healthz" and c0(n).get("readinessProbe", {}).get("httpGet", {}).get("path") == "/readyz"
    and c0(n)["livenessProbe"]["httpGet"]["port"] == SERVICES[n] == c0(n)["readinessProbe"]["httpGet"]["port"] for n in deps), "liveness must NOT call /readyz")
check("every container has CPU and memory requests and a memory limit", all(
    {"cpu", "memory"} <= set(c0(n).get("resources", {}).get("requests", {})) and "memory" in c0(n).get("resources", {}).get("limits", {}) for n in deps))
check("every container runs as non-root and cannot escalate privileges", all(
    (c0(n).get("securityContext", {}).get("runAsNonRoot") or deps[n]["spec"]["template"]["spec"].get("securityContext", {}).get("runAsNonRoot"))
    and c0(n).get("securityContext", {}).get("allowPrivilegeEscalation") is False for n in deps))
check("gateway, menu and payments run 2 replicas or more", all(deps[n]["spec"]["replicas"] >= 2 for n in ("gateway", "menu", "payments")))


def envs(n):
    return {e["name"]: e.get("value", "") for e in c0(n).get("env", [])}


want = {"gateway": {"MENU_URL": "menu", "ORDERS_URL": "orders"}, "orders": {"MENU_URL": "menu", "PAYMENTS_URL": "payments", "NOTIFICATIONS_URL": "notifications"}}
check("gateway and orders reach the others by Service name, never by IP", all(
    re.match(r"^http://%s(\.%s)?(\.svc(\.cluster\.local)?)?:%d" % (h, NS, SERVICES[h]), envs(n).get(var, "")) for n, m in want.items() for var, h in m.items()))
ready = wait_for(lambda: all((kj("get", "deployment", n, "-n", NS) or {}).get("status", {}).get("readyReplicas", 0) >= deps[n]["spec"]["replicas"] for n in deps), 120)
svcs = {s["metadata"]["name"]: s for s in (kj("get", "services", "-n", NS) or {}).get("items", [])}
eps = {e["metadata"]["name"]: e for e in (kj("get", "endpoints", "-n", NS) or {}).get("items", [])}
check("a Service for each, on the right port, with ready endpoints behind it", all(
    n in svcs and svcs[n]["spec"]["ports"][0]["port"] == p and any(s.get("addresses") for s in eps.get(n, {}).get("subsets", [])) for n, p in SERVICES.items()),
    "kubectl get endpoints -n beanie")
check("all pods become Ready", ready, "kubectl get pods -n beanie")
if not ready:
    finish()

print("== Live: place an order through the gateway ==")
port = free_port()
pf = subprocess.Popen(["kubectl", "port-forward", "-n", NS, "svc/gateway", "%d:8000" % port], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
base = "http://127.0.0.1:%d" % port
try:
    wait_for(lambda: http(base + "/healthz")[0] == 200, 20, 1)
    st, body = http(base + "/api/menu")
    check("GET /api/menu answers 200 with items", st == 200 and "flat-white" in body, "got %s" % st)
    order = json.dumps({"customer": "Ana", "items": [{"item_id": "flat-white", "quantity": 2}]}).encode()
    st, body = http(base + "/api/orders", order)
    check("POST /api/orders is paid (201)", st == 201, "got %s %s" % (st, body[:80]))
    st, _ = http(base + "/api/orders", json.dumps({"customer": "Bo", "items": [{"item_id": "flat-white", "quantity": 1}], "card_token": "tok_declined"}).encode())
    check("a declined card is 402", st == 402)

    print("== Break 1: kill a menu pod while traffic flows ==")
    pods = [p["metadata"]["name"] for p in (kj("get", "pods", "-n", NS, "-l", "app=menu") or {}).get("items", [])]
    k("delete", "pod", pods[0], "-n", NS, "--wait=false")
    bad = 0
    t_end = time.time() + 12
    while time.time() < t_end:
        if http(base + "/api/menu", timeout=3)[0] != 200:
            bad += 1
        time.sleep(0.4)
    check("at most one request failed while a menu pod was deleted (the other replica served)", bad <= 1, "%d failed" % bad)
    back = wait_for(lambda: (kj("get", "deployment", "menu", "-n", NS) or {}).get("status", {}).get("readyReplicas", 0) >= deps["menu"]["spec"]["replicas"], 90)
    check("the Deployment created a replacement and menu is back to its replicas", back)

    print("== Break 2: take menu away ==")
    gw_before = {p["metadata"]["name"]: p["status"]["containerStatuses"][0]["restartCount"] for p in (kj("get", "pods", "-n", NS, "-l", "app=gateway") or {}).get("items", [])}
    n_menu = deps["menu"]["spec"]["replicas"]
    k("scale", "deployment/menu", "-n", NS, "--replicas=0")
    def gw_not_ready():
        items = (kj("get", "pods", "-n", NS, "-l", "app=gateway") or {}).get("items", [])
        return items and all(not all(c["ready"] for c in p["status"].get("containerStatuses", [])) for p in items)
    nr = wait_for(gw_not_ready, 100)
    check("gateway pods turn NotReady when menu is gone (readiness looks at dependencies)", nr)
    time.sleep(45)  # long enough for a liveness probe that depends on menu to restart the gateway (3 failures x 10 s)
    gw_after = {p["metadata"]["name"]: p["status"]["containerStatuses"][0]["restartCount"] for p in (kj("get", "pods", "-n", NS, "-l", "app=gateway") or {}).get("items", [])}
    check("... and the gateway was NOT restarted (liveness ignores dependencies)", gw_before == gw_after, "restarts before %s after %s" % (gw_before, gw_after))
    k("scale", "deployment/menu", "-n", NS, "--replicas=%d" % n_menu)
    ok = wait_for(lambda: (kj("get", "deployment", "gateway", "-n", NS) or {}).get("status", {}).get("readyReplicas", 0) >= deps["gateway"]["spec"]["replicas"] and (kj("get", "deployment", "menu", "-n", NS) or {}).get("status", {}).get("readyReplicas", 0) >= n_menu, 120)
    check("after menu comes back, the gateway is Ready again without anybody touching it", ok)

    print("== Break 3: ship an image that does not exist ==")
    k("set", "image", "deployment/payments", "*=%s:does-not-exist" % IMG.rsplit(":", 1)[0], "-n", NS)
    time.sleep(25)
    pods = (kj("get", "pods", "-n", NS, "-l", "app=payments") or {}).get("items", [])
    st, _ = http(base + "/api/orders", order, timeout=12)
    check("orders still work while the bad rollout is stuck (old pods kept serving)", st == 201, "got %s" % st)
    check("the bad pods never became Ready (ImagePullBackOff / ErrImagePull)", any(
        (p["status"].get("containerStatuses") or [{}])[0].get("state", {}).get("waiting", {}).get("reason") in ("ImagePullBackOff", "ErrImagePull") for p in pods))
    rc, out, _ = k("rollout", "undo", "deployment/payments", "-n", NS)
    done = wait_for(lambda: k("rollout", "status", "deployment/payments", "-n", NS, "--timeout=5s")[0] == 0, 120)
    img_now = (kj("get", "deployment", "payments", "-n", NS) or {}).get("spec", {}).get("template", {}).get("spec", {}).get("containers", [{}])[0].get("image")
    check("rollout undo brought the good image back", rc == 0 and done and img_now == IMG, "image: %s" % img_now)
    st, _ = http(base + "/api/orders", order)
    check("an order is paid after the rollback", st == 201)
finally:
    pf.terminate()
finish()
