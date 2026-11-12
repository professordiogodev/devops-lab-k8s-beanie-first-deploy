# LAB | Kubernetes: Beanie Goes Live on Friday

## The situation

```text
PRE-FLIGHT CHECKLIST - Beanie on Kubernetes             Friday, departure Saturday 8:00
[ ] Five services deployed: gateway (the only public door), menu, orders,
    payments, notifications
[ ] A pod dies             -> orders keep coming in
[ ] A dependency vanishes  -> orders keep coming in
[ ] A broken release ships -> orders keep coming in
Crew   : nobody will watch it
Tower  : a checker that does all three things to your cluster, on purpose
```

Beanie is a cafe ordering system made of five small services that call each other. It works on a laptop with one command. On Friday it moves to Kubernetes, and on Saturday morning the queue starts at 8:00. You write the manifests; the checker will then do the three things on the list to your cluster while orders keep coming in.

> **Your mission**
> - Build the Beanie image and write a Deployment and a Service for each of the five services
> - Give every container two different probes, honest resource numbers and no root
> - Place an order through the gateway
> - Watch Kubernetes heal a killed pod, stay calm when a dependency is gone, and refuse a release that cannot start
> - Tear it all down and prove it

**Time:** 105-120 min | **Cost:** free on a local cluster | **You need:** Docker, `kubectl`, git, curl, Python 3 and a local Kubernetes cluster running (kind, OrbStack or Docker Desktop with Kubernetes enabled). Check with `kubectl get nodes`.

---

## Part 0 - The image and the cluster

Fork this repository, clone your fork, and run:

```bash
./setup.sh
```

It clones Beanie (version 0.1.0) into `beanie/`, builds **one** image from the provided `Dockerfile` (the command decides which of the five services runs: `python -m beanie menu`, `... orders`, and so on) and, if your cluster is kind, loads it into the cluster. It prints the image name to use in your manifests and writes it to `.image`.

Read the `Dockerfile`: it is short. Why does it use a numeric user (`USER 10001`) and not a name? (Hint: look up what `runAsNonRoot` can verify.)

> **Think** Five services, one image. What do you gain compared with five images, and what do you give up? When would you split them?

---

## Part 1 - Read the model, write four more

`k8s/00-namespace.yaml` creates the namespace (why is the file called `00-...`? `kubectl apply -f k8s/` applies files in alphabetical order). `k8s/menu.yaml` is complete: a Deployment and a Service. Read **every** line, then read `k8s/TODO.md`, which says what the other four need. The numbers that matter:

| Service | Port | Replicas |
|---------|------|----------|
| menu | 8001 | 2 |
| payments | 8003 | 2 |
| notifications | 8004 | 1 |
| orders | 8002 | 1 |
| gateway | 8000 | 2 |

Things to get right, because the checker will:

1. **Liveness** calls `/healthz`, **readiness** calls `/readyz`. They are not interchangeable (Part 3 shows why).
2. `orders` and `gateway` find the others **by Service name** (`http://menu:8001`), set through environment variables (`MENU_URL`, `ORDERS_URL`, `PAYMENTS_URL`, `NOTIFICATIONS_URL`). Never an IP address: pod IPs change every time a pod is replaced.
3. CPU and memory **requests**, and a memory **limit**. The scheduler places pods using the requests; the kernel enforces the limits.
4. `runAsNonRoot: true` and `allowPrivilegeEscalation: false`.

```bash
kubectl apply -f k8s/
kubectl get pods -n beanie -w
```

> **Predict** `orders` has one replica on purpose. Beanie keeps orders in the memory of the process unless it has a database. If you ran two replicas, what would `GET /api/orders` show, depending on which pod answered? (The next lab fixes this properly. Do not "fix" it here by adding a database.)

---

## Part 2 - Place an order

The gateway is the only public door, but your cluster has no load balancer. Use a port-forward to reach the Service:

```bash
kubectl port-forward -n beanie svc/gateway 8000:8000
```

In another terminal:

```bash
curl -s localhost:8000/api/menu
curl -s -X POST localhost:8000/api/orders -H 'Content-Type: application/json' \
  -d '{"customer": "Ana", "items": [{"item_id": "flat-white", "quantity": 2}]}'
kubectl logs -n beanie deploy/notifications --tail=3
```

Follow the order: the gateway called orders, orders called menu (price), payments (charge) and notifications (tell the customer). Find the three log lines that prove it, and find the `request_id` that is the same in all of them.

Try the card `tok_declined` and the card `tok_slow`. What does each return, and how long does the slow one take?

> **Think** Inside the cluster, the gateway reaches `http://menu:8001`. Who turns the name `menu` into an address? What happens to that address when a menu pod is replaced?

---

## Part 3 - Break it before Saturday does

Do these by hand first. Keep a request loop running in a second terminal so you feel what customers feel:

```bash
while true; do curl -s -o /dev/null -w "%{http_code}\n" localhost:8000/api/menu; sleep 0.3; done
```

**A. A pod dies.** Delete a menu pod: `kubectl delete pod -n beanie <a menu pod>`. Watch the loop and `kubectl get pods`. Who made the new pod, and why did the loop barely notice?

**B. A dependency disappears.** `kubectl scale -n beanie deployment/menu --replicas=0`. Watch the gateway pods: `kubectl get pods -n beanie -w`. After a short while they become `0/1` Ready, but the `RESTARTS` column stays at 0. Now scale menu back up and watch them recover without anyone touching them.

> **Think** The gateway was *alive* all along (`/healthz` answered) but not *ready* (`/readyz` said 503, because its dependency was gone). Kubernetes took it out of the Service, so no customer got an error page from a half-working pod. What would have happened if you had pointed the **liveness** probe at `/readyz`? Picture all the gateway pods, a menu outage and a restart loop.

**C. A bad release.** Somebody types a wrong tag:

```bash
kubectl set image -n beanie deployment/payments '*=beanie:does-not-exist'
kubectl rollout status -n beanie deployment/payments --timeout=30s
kubectl get pods -n beanie
```

New pods go `ErrImagePull`, then `ImagePullBackOff`. The old pods are still there and still serve. Place an order: it works. Then go back:

```bash
kubectl rollout undo -n beanie deployment/payments
kubectl rollout history -n beanie deployment/payments
```

> **Predict** Why did the old payments pods survive the bad rollout? Count how many pods the default rolling-update strategy is allowed to take away at the same time with 2 replicas (`maxUnavailable` is 25%, rounded down). What would a single replica have done?

---

## Part 4 - Prove it

```bash
./verify.sh
```

It reads your Deployments and Services as the cluster stores them, places orders through the gateway, and then does A, B and C to your cluster itself, restoring each. Fix what is red and run it again until it ends with **ALL CHECKS PASSED**.

> **Stuck?** `ImagePullBackOff` on every pod: the image in your manifests is not the one in `.image` (on kind, run `./setup.sh` again to load it). Pods `Running` but never `Ready`: check the probe port and path, `kubectl describe pod`, and `kubectl logs`. The gateway answers 503: orders or menu not Ready, or a wrong Service name in the environment (`kubectl exec` into a pod and `getent hosts menu`). `Insufficient memory/cpu`: lower the requests.

---

## Level up (optional)

- Add a `PodDisruptionBudget` for menu so `kubectl drain` can never take both pods at once. Test it with `kubectl drain` on kind (add a worker node first).
- Add `topologySpreadConstraints` so the two gateway pods land on different nodes.
- Add `startupProbe` to orders and set the liveness probe to something stricter once it has started. What does `startupProbe` stop the liveness probe from doing during a slow start?
- Run `kubectl get deployment menu -o yaml` and delete from your manifest everything the cluster would default anyway. What is left?

<!-- teardown:start (generated by labs.py, do not edit) -->
## Tear down (mandatory)

Resources left behind cost money, keep doors open and pollute the next lab. Removing what you created is part of the job, so it is part of the submission: **you must prove it is gone**.

Do this **last**, after you have pasted your `verify` output into `SUBMISSION.md` (once you tear down, the lab can no longer be verified).

1. Run `./teardown.sh`. It deletes the `beanie` namespace (everything in it), the port-forwards it started and the cloned Beanie source.

Then run the proof:

```bash
./verify-teardown.sh
```

It prints a list of checks and must end with **TEARDOWN VERIFIED**. If it reports leftovers, remove them and run it again. Paste the full output in your submission.
<!-- teardown:end -->

<!-- submission:start (generated by labs.py, do not edit) -->
## Submission

Answer the questions in `SUBMISSION.md` in **your fork** (paste output in code blocks where asked), push, then submit the **URL of your fork**.

**Files to commit**

- `k8s/` with your manifests (a Deployment and a Service per service, in a namespace)
- `notes.md` with your commands and what you saw (optional)

**Questions to answer**

1. Paste `kubectl get pods,svc -n beanie` and one order placed through the gateway. How does the gateway find the menu service: what is the URL in its environment and who resolves the name?
2. Delete one `menu` pod while a loop of requests runs. Paste what the loop showed and `kubectl get pods`. Which controller created the replacement and why did customers not notice?
3. Scale `menu` to 0. Paste `kubectl get pods -n beanie` for the gateway before and after, and its `RESTARTS` column. Why is the gateway NotReady but not restarted, and what would a liveness probe that called `/readyz` have done to your cluster?
4. Roll out an image tag that does not exist for `payments` (`kubectl set image`). Paste `kubectl rollout status` and `kubectl get pods`. Why did orders keep working, and which two settings of your Deployment made that true? Then roll back and paste the command.
5. You set resource requests and limits. What happens to a pod that exceeds its memory limit, and to one that exceeds its CPU limit? What does the scheduler use the requests for?
6. Why does a Service of type ClusterIP not need you to know any pod IP, and what would break if you hard-coded one?
7. Paste the output of `./verify.sh`. It must end with **ALL CHECKS PASSED**.
8. **Tear down.** Paste the output of `./verify-teardown.sh`. It must end with **TEARDOWN VERIFIED**.
<!-- submission:end -->
