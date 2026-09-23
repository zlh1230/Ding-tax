# DingTalk setup

These steps apply only after the organization administrator confirms the current screens and permissions in the official developer console.

1. Create or confirm an enterprise internal Micro App and configure its H5 homepage and PC homepage. Add `?corpid=$CORPID$` as described by the official `requestAuthCode` Explorer when applicable.
2. Configure the production HTTPS homepage URL and the local development URL according to the current console rules. **TO_VERIFY:** exact localhost/tunnel requirements.
3. Set application visibility to the intended invoice operators; backend allowlist remains mandatory.
4. Obtain CorpId, Client ID, Client Secret and the invoice approval ProcessCode from the developer console. Put them only in ignored local configuration, never Git.
5. In the API Explorer, grant and verify the current user identity and approval-instance list/detail permissions for the target process code. **TO_VERIFY:** exact scope names, pagination and throttling limits.
6. Capture one approved test approval detail payload, redact any credentials, and use it to complete the live adapter response mapping before enabling production sync.

Required local settings are documented in `backend/.env.example`. `DINGTALK_ALLOWED_USER_IDS` is a comma-separated backend allowlist.
