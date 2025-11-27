# REST / JWT Access Setup for Scratch Orgs (Actionable Guide)

Use this checklist to get a scratch org ready for REST/Bulk/Composite access with JWT (no refresh tokens, no client secret). Follow in order; copy values into `agents/python/.env` when prompted.

## Prerequisites
- Salesforce CLI installed (`sf` v2 or newer).  
- Dev Hub authenticated: `sf org login web --alias DevHub --set-default-dev-hub true`.
- Your key pair already exists (generated earlier):  
  - Private key: `config/server.key` (keep secret)  
  - Public cert: `config/server.crt` (upload to Connected App)

## Step 1 — Create or refresh a scratch org
```bash
sf org create scratch --definition-file config/project-scratch-def.json --alias MyScratch --duration-days 7 --set-default
sf org open --target-org MyScratch
```

## Step 2 — Create the External Client App (new Connected App UI)
**If you’re on the “External Client App Settings” page:**  
 - Turn **Allow creation of connected apps** = **On**.  
 - Leave both “Allow access to External Client App consumer secrets…” toggles **Off** (safer defaults).  
 - Click **Save**, then go to **Setup → App Manager**.

Create the app:
1) In **Setup → App Manager**, click **New External Client App** (top right).  
2) Fill basics:  
   - **External Client App Name**: `AgentJWTApp`  
   - **API Name**: auto-fills  
   - **Contact Email**: your email  
   - **Distribution State**: **Local** (for this org)
3) Expand **API (Enable OAuth Settings)**:  
   - Check **Enable OAuth** (this reveals Callback).  
   - **Callback URL**: required but unused for JWT; use `http://localhost:1717/callback` (or `https://login.salesforce.com/services/oauth2/success`).  
   - **Selected OAuth Scopes**: move to Selected → `api`, `refresh_token offline_access`; optionally add `chatter_api`, `openid`, `id`.  
     - Bulk API 1.0/2.0 is covered by `api`; the old `bulk_api` scope no longer appears.  
   - Check **Use digital signatures** and upload `config/server.crt`.  
   - Leave the client secret as-is (JWT ignores it).  
   - Leave **Require Secret for Web Server Flow** and **Require Secret for Refresh Token Flow** checked (defaults; harmless for JWT).  
   - Leave **PKCE** unchecked (not used by JWT).  
   - Leave **Enable for Device Flow** unchecked (not needed).  
4) Save. Wait 2–10 minutes for activation, then retrieve the **Consumer Key** (`SF_CLIENT_ID`): **Setup → App Manager → find AgentJWTApp → ▼ → View → Manage Consumer Details** (may prompt for your password). Use the Consumer Key only; the secret isn’t used for JWT.  
5) If your org enforces “Installed apps” (some orgs after Sept 2025): **Setup → Connected Apps OAuth Usage → AgentJWTApp → Install**. If blocked, grant your user **Approve Uninstalled Connected Apps** or **Use Any API Client**; if no Install button is present, you can skip this step.

## Step 3 — Authorize the user (required for JWT)
1) In the Connected App detail (**Manage → Edit Policies**):
   - **Permitted Users**: set to **Admin approved users are pre-authorized**.  
   - Under **Profiles**, check **System Administrator** (and any other profile your SF_USERNAME has).  
   - **IP Relaxation**: set to **Relax IP restrictions** unless you must enforce allowlists.  
   - **High assurance session required**: leave **unchecked** (JWT/API calls don’t carry MFA).
2) If your org shows **Connected Apps OAuth Usage → AgentJWTApp → Install**, click **Install** (some orgs after Sept 2025 require this). If blocked, grant yourself **Approve Uninstalled Connected Apps** or **Use Any API Client** temporarily.

## Step 4 — Fill your env template
Edit `agents/python/.env` (copy from `.env.template`) with:
- `SF_CLIENT_ID` = Connected App Consumer Key (from **Manage Consumer Details**)  
- `SF_USERNAME` = the scratch org user you will authenticate as (shown in `sf org display --target-org MyScratch`, e.g., `test-abc123@example.com`)  
- `SF_LOGIN_URL` = token endpoint you will post to, in `https://...` form. For this scratch org, use its My Domain login host, e.g., `https://platform-ruby-8349-dev-ed.scratch.my.salesforce.com`. `https://login.salesforce.com` also works for production-type scratch orgs, but match it with audience.  
- `SF_AUDIENCE` = must match the login host **including https://** (same as `SF_LOGIN_URL`).  
- `SF_JWT_KEY_PATH` = `../config/server.key`  
- `SF_API_VERSION` = `65.0` (or current)
- After the JWT call, use the **instanceUrl** returned in the response for all REST/Bulk/Composite data calls; `SF_LOGIN_URL` is only for obtaining the token.

## Step 5 — Get an access token via JWT (Python/Postman/loader)
- POST to `${SF_LOGIN_URL}/services/oauth2/token` with form data:  
  - `grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer`  
  - `assertion=<base64url-encoded JWT signed with config/server.key>`  
    - JWT claims: `iss=SF_CLIENT_ID`, `sub=SF_USERNAME`, `aud=SF_AUDIENCE`, `exp` about 5 minutes ahead.  
- Response contains `access_token` and `instance_url`. Use `instance_url` for all data calls.  
- If you get `audience` errors, ensure `SF_AUDIENCE` matches the host in `SF_LOGIN_URL`. If `invalid_grant`, recheck scopes, cert upload, and user/profile access.

## Step 6 — Ready for REST/Bulk/Composite calls
- Base URL: use the `instanceUrl` from the login response.  
- Bulk API 2.0: `POST /services/data/v65.0/jobs/ingest` (operation `upsert`, `externalIdFieldName` set).  
- Composite Tree/Graph: `/services/data/v65.0/composite/tree/{Object}` or `/composite/graph`.  
- Identity check: `GET /services/oauth2/userinfo` to verify token scope and user.

## Step 7 — Security housekeeping
- Keep `config/server.key` and `.env` out of git (already ignored).  
- Rotate the key yearly: generate a new keypair, upload new cert to the Connected App, update `SF_JWT_KEY_PATH`, and remove the old cert after cutover.  
- Limit IP ranges and session policies in the Connected App if your org security policy requires it.

You can now run loaders from `agents/python/` (or Postman/cURL) using JWT tokens to populate the scratch org without any Apex. Save this doc for future scratch org spins.
