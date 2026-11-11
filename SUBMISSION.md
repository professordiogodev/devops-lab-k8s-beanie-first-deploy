# Submission

Fork URL: <!-- paste the URL of your fork here -->

## Files to commit

- [ ] `k8s/` with your manifests (a Deployment and a Service per service, in a namespace)
- [ ] `notes.md` with your commands and what you saw (optional)

## Questions

Answer in your own words. Where a question asks for output, paste it in a code block.

### Q1. Paste `kubectl get pods,svc -n beanie` and one order placed through the gateway. How does the gateway find the menu service: what is the URL in its environment and who resolves the name?

**Your answer:**

<!-- replace this line with your answer -->

### Q2. Delete one `menu` pod while a loop of requests runs. Paste what the loop showed and `kubectl get pods`. Which controller created the replacement and why did customers not notice?

**Your answer:**

<!-- replace this line with your answer -->

### Q3. Scale `menu` to 0. Paste `kubectl get pods -n beanie` for the gateway before and after, and its `RESTARTS` column. Why is the gateway NotReady but not restarted, and what would a liveness probe that called `/readyz` have done to your cluster?

**Your answer:**

<!-- replace this line with your answer -->

### Q4. Roll out an image tag that does not exist for `payments` (`kubectl set image`). Paste `kubectl rollout status` and `kubectl get pods`. Why did orders keep working, and which two settings of your Deployment made that true? Then roll back and paste the command.

**Your answer:**

<!-- replace this line with your answer -->

### Q5. You set resource requests and limits. What happens to a pod that exceeds its memory limit, and to one that exceeds its CPU limit? What does the scheduler use the requests for?

**Your answer:**

<!-- replace this line with your answer -->

### Q6. Why does a Service of type ClusterIP not need you to know any pod IP, and what would break if you hard-coded one?

**Your answer:**

<!-- replace this line with your answer -->

### Q7. Paste the output of `./verify.sh`. It must end with **ALL CHECKS PASSED**.

**Your answer:**

<!-- replace this line with your answer -->

### Q8. **Tear down.** Paste the output of `./verify-teardown.sh`. It must end with **TEARDOWN VERIFIED**.

**Your answer:**

<!-- replace this line with your answer -->
