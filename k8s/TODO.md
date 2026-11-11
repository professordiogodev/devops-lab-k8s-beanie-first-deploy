# What to write in this folder

`00-namespace.yaml` creates the namespace (its name sorts first on purpose). `menu.yaml` is complete and is your model. Write the other four, one file each:

| File | Service | Port | Replicas | Environment it needs |
|------|---------|------|----------|----------------------|
| `payments.yaml` | `payments` | 8003 | 2 | nothing |
| `notifications.yaml` | `notifications` | 8004 | 1 | nothing |
| `orders.yaml` | `orders` | 8002 | 1 (see the lab: why one) | `MENU_URL`, `PAYMENTS_URL`, `NOTIFICATIONS_URL` |
| `gateway.yaml` | `gateway` | 8000 | 2 | `MENU_URL`, `ORDERS_URL` |

The URLs use the **Service names**, for example `http://menu:8001` (Kubernetes DNS resolves them inside the namespace). Every Deployment needs both probes, resource requests and a memory limit, and `runAsNonRoot`.

Each service: a Deployment and a Service in the namespace `beanie`.
