# Runtime

Fresh provisioning for CLIProxyAPI and T3, without adopting or replacing an existing unknown runtime.

```bash
./install.sh --only runtime.proxy --stage install --apply
./install.sh --only runtime.proxy --stage configure --apply
# Install dev-tools.t3code first, then explicitly permit its supported installer to start it:
./install.sh --only runtime.t3 --stage configure --set runtime.start_services=true --apply
./install.sh --only runtime --stage verify
```

CLIProxyAPI is pinned and downloaded with the upstream GitHub asset SHA-256 digest. Its generated API key/environment file and config are private. The proxy binds loopback; it is not exposed to the network. Provider authentication remains interactive. Existing unmanaged binaries/configuration are preserved and cause setup to stop rather than reset credentials or providers. Generated files have hash stamps; editing one makes future automated overwrite fail.

T3's supported `t3 service install` owns its launcher. It starts a missing service, so that action requires `runtime.start_services=true`; existing healthy services are only started idempotently. Our drop-ins set the port, proxy environment, optional server resource limits and dependency ordering. A bounded local API gate authenticates to the proxy before T3 starts; it accepts an empty provider-model list so onboarding works without Internet/provider enrollment. Startup health separately requires a nonempty model list before reporting ready. A failed upstream request never causes a whole-stack restart.

The gate is checked when its service starts; it is not an upstream watchdog. To retry a failed startup gate after fixing local configuration, use `agentic-startup start` when workspace management is installed, or `systemctl --user start t3code`. Port/config changes to already-running services require a deliberate restart after saving work. Existing T3 tunnel preferences are retained; configure a new T3 Connect identity through T3 itself. External authenticated UI health must be tested from another device.

Zero resource overrides retain T3's native limits. `runtime.limits` applies to the server cgroup; T3 agents run in separate native scopes/slices. `storage.limits` optionally adjusts aggregate agent CPU/I/O fairness while retaining T3's memory budgets. Do not set server memory limits from a guess about total agent RAM.
