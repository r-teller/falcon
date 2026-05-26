# Security Blueprint

Purpose: This file establishes the security rules and best practices to keep the application and its user data safe.

> Use this file to outline the security practices for your project. Thinking about security early helps prevent problems later. This file has highest precedence in the conflict-resolution matrix (see [`claude.md`](claude.md)).
>
> Example blocks below are themed for the worked Asteroids example — swap each `<!-- theme example -->...<!-- /theme example -->` block with your project's actual posture.

## 0. Baseline Best Practices

Here are a few universal rules that apply to every application and product we will build.

- **Never Hardcode Secrets:** Never write API keys, passwords, or other secrets directly in your source code.
- **Use a `.gitignore` file:** Your project's `.gitignore` file **must** include entries for any files that contain secrets, such as `.env`, `.env.local`, or `*.pem`. This prevents them from ever being committed to Git.
- **Use Environment Variables:** Load secrets from environment variables. For local development, use a `.env` file to store these variables. In production, your hosting provider (like Vercel, AWS, or GCP) will have a secure way to set them.
- **Apply the Principle of Least Privilege:** Create API keys and credentials with the minimum permissions they need to function. For example, if a key only needs to read data, do not give it permission to write or delete data.

---

## 1. Data Sensitivity Level

> First, let's classify the kind of data your application will handle. This helps determine how strict our security measures need to be.

- **My Project's Data is:** [e.g., Public, Internal, Confidential, Sensitive/PII]

<!-- theme example -->
- **_Asteroids: Wave Defense:_**
  **My Project's Data is: Sensitive/PII.** The application stores player email addresses (from OAuth), display names, replay artifacts, and purchase history. Replay artifacts are not PII per se but combined with the player identity become identifying. PII handling follows GDPR principles even though the player base is global.
<!-- /theme example -->

---

## 2. Authentication & Authorization (Who are you & what can you do?)

> **Authentication** is about verifying who a user is (like logging in). **Authorization** is about what an authenticated user is allowed to do (like viewing a specific page).

- **Authentication Method:** [e.g., None, Simple Password, OAuth, Supabase Auth]
- **Authorization Rules:** [e.g., All users can do everything, Only logged-in users can see content, Users can only edit their own data]

<!-- theme example -->
- **_Asteroids: Wave Defense:_**
  **Authentication Method: Supabase Auth.** Players sign in via Apple OAuth, Google OAuth, or Steam OpenID. No local password storage. JWT tokens with 1-hour expiry + 30-day refresh token.
  **Authorization Rules:**
  - Players can read all public leaderboards, write their own replays + purchases
  - Players can soft-delete their own account (replay artifacts anonymized, leaderboard rank preserved as "Anonymous Player")
  - Replay-validator service accounts can read replay artifacts + write `ReplayResult`; they CANNOT modify `LeaderboardEntry` directly (a separate scoring service does that on `passed` results)
  - Server operators have read-only access to all player data via audit-logged queries
<!-- /theme example -->

---

## 3. Project-Specific Security Concerns

> Beyond auth and secrets, are there project-specific security concerns that need their own treatment? (Anti-cheat, PII redaction, content moderation, etc.) Capture them here.

<!-- theme example -->
- **_Asteroids: Wave Defense — Anti-Cheat:_**
  The replay-validator IS the anti-cheat system. Strategy:
  - **Deterministic physics** — same seed + same inputs = same outcome, byte-identical
  - **Server-side replay re-run** — every submitted replay is re-executed by the validator against the canonical `wave_pack_version` before the score lands on the leaderboard
  - **Input bounds checking** — input rate, click positions, and timestamps must fall within physical-possibility bounds before validation proceeds
  - **Signature verification** — replays are signed at capture time with a per-session key; tampered replays fail signature check before validation
  - **No client-side score reporting** — the score is computed by the server during validation; the client UI displays it, doesn't compute it

  Suspicious patterns are logged to a separate audit table; persistent abusers are flagged for human review (not auto-banned).
<!-- /theme example -->

---

## 4. Dependency & Supply Chain Security

> Your project uses code from other developers (dependencies). We need a plan to make sure those dependencies are safe.

- **How We Check Dependencies:** [e.g., Manual review, `npm audit`, GitHub Dependabot]
- **Rule for Adding New Dependencies:** [e.g., Any developer can add them, Must be approved by the project lead]

<!-- theme example -->
- **_Asteroids: Wave Defense:_**
  **How we check dependencies: GitHub Dependabot** for `npm` + `pip`; manual review for new direct dependencies.
  **Rule for adding new dependencies:** Must be reviewed for maintenance status, bundle size, and security advisories before merging the bead that introduces them. New cryptography or auth dependencies require a separate decision (spike) bead.
<!-- /theme example -->

---

## 5. Secrets Management & Best Practices

> "Secrets" are sensitive pieces of information like API keys, database passwords, or access tokens. We must **never** write them directly in our code or commit them to version control.

- **Where Secrets are Stored:** [e.g., In a local `.env` file, Vercel Environment Variables, AWS Secrets Manager]
- **Who Has Access to Secrets:** [e.g., Only me, The development team]

<!-- theme example -->
- **_Asteroids: Wave Defense:_**
  **Where Secrets are Stored:** GCP Secret Manager (production), `.env.local` files (local development, gitignored). CI/CD secrets in GitHub Actions encrypted environment variables.
  **Who Has Access to Secrets:** Production secrets — server operators only (audit-logged access). Development secrets — full dev team via 1Password shared vault.
  **Rotation policy:** OAuth client secrets rotated annually OR on personnel change; JWT signing key rotated quarterly; replay-signing key rotated only on suspected compromise (rotation invalidates all in-flight replays).
<!-- /theme example -->

---

## 6. Logged-Out / Anonymous Capabilities

> What can a user do *without* signing in? Spelling this out forces a conscious decision about the public surface.

<!-- theme example -->
- **_Asteroids: Wave Defense:_**
  - Browse public leaderboards (read-only)
  - Watch replays (read-only, no playback persistence)
  - Try the tutorial wave-pack (local-only; no score submission)

  Everything else requires authentication.
<!-- /theme example -->
