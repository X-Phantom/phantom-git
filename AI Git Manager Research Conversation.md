---
title: "Fixing GitHub Actions CI Failures"
id: "bda60104e891379d"
provider: "gemini"
updated: "2026-11-14T08:23:01.574Z"
tags:
  - gemini-export
---

# Fixing GitHub Actions CI Failures

## 👤 You

So I just set up this new repository on GitHub and I uploaded my web app to it and I'm constantly getting emails from GitHub that have the following messages in it:  
  
 "CI Pipeline - The Phantom Labs / Unit &amp; Component Tests  
Failed in 1 minute and 24 seconds  
  
CI Pipeline - The Phantom Labs / Code Quality &amp; Type Integrity  
Failed in 1 minute and 34 seconds  
  
CI Pipeline - The Phantom Labs / Production Standalone Build  
Skipped"

## 🤖 Assistant

Your web app repository (**X-Phantom/Phantom-Labs-Webapp**) includes an automated **GitHub Actions** workflow file (located in the `.github/workflows` folder of your project). Every time you upload or push changes to the `main` branch, GitHub automatically runs a Continuous Integration (CI) pipeline to test and build your app.

Here is what those three status messages mean:

- **Unit &amp; Component Tests (Failed):** The automated test runner executed your app's test suite, and either a test failed, a dependency was missing, or no test script was configured.
- **Code Quality &amp; Type Integrity (Failed):** The linter or TypeScript compiler found formatting issues, syntax errors, or type mismatches in your code.
- **Production Standalone Build (Skipped):** Because the build step is configured to depend on the first two checks passing, GitHub automatically skipped building the app once the earlier checks failed.

Depending on whether you want to fix the errors or just stop the emails, follow one of the options below.

---

### Option 1: View the Exact Error Logs to Fix the Pipeline

If you want the automated checks to pass, you need to see which specific test or file is triggering the failure.

---

### Option 2: Disable the Workflow (If You Don't Need Automated Testing Yet)

If your web app was generated from a template or boilerplate that included a CI pipeline you don't actually want running on every upload, you can turn the workflow off completely.

---

### Option 3: Keep the Pipeline Running, but Stop the Emails

If you want the checks to keep running on GitHub without cluttering your inbox, you can turn off email alerts for GitHub Actions.

If you want to fix the errors rather than disabling the pipeline, feel free to paste the error text or share a screenshot from the failed step in the **Actions** tab so we can pinpoint the exact fix.

## 👤 You

I want to understand the right thing to do here. I am new to development and I have recently started using github and am trying to integrate it into my development process. I have all my development done through AI and I wanna understand how accurate is git hub actions against my webapp that has been developed through AI should I ensure that these tests pass or is it common to ignore them. What factors should I take into consideration when github actions suggest this sort of CI failures

## 🤖 Assistant

Building software primarily with AI is a great way to move fast, and running into CI (Continuous Integration) failures right after pushing to GitHub is one of the most common hurdles for new developers using AI tools.

**GitHub Actions is 100% objective**, because it isn't "guessing" about your code—it is spinning up a brand-new, blank virtual computer in the cloud, downloading your repository, and running the exact commands defined in your project (`npm test`, `npm run lint`, `tsc`, `npm run build`). However, just because a check fails on GitHub doesn't automatically mean your web app is broken for users.

**Ignoring a failing CI pipeline while leaving it turned on is an anti-pattern.** If you train yourself to ignore failure emails, you'll eventually miss a failure that actually breaks your live site, while wasting your free GitHub Actions compute minutes on every push. Instead, the standard practice is to **either fix the pipeline (or ask your AI to fix it) so it turns green, or disable the noisy checks until your project actually needs them.**

When your entire codebase is generated and maintained by AI, several distinct mechanisms explain why these three specific jobs react the way they do.

- **Code Quality &amp; Type Integrity (High Value — Worth Fixing):** AI coding assistants are great at making a page look and work right in the browser, but they frequently leave behind small messes: unused variables, imported libraries you later removed, or mismatched TypeScript types (e.g., passing text where a number was expected). Many local development servers let your app run anyway in the browser even when TypeScript or ESLint complains. When GitHub runs **Code Quality &amp; Type Integrity**, it enforces strict rules. Fixing this is genuinely valuable because TypeScript and linter errors are early warning signs of real bugs, and you can simply copy-paste the error log from GitHub back into your AI assistant and say, *"Fix these type and lint errors."*
- **Unit &amp; Component Tests (Context-Dependent — Check for "Stale" Tests):** When an AI scaffolds a project or uses a template, it often generates placeholder unit tests (for example, a test that checks if the page says `"Welcome to App"`). Later, you prompt the AI to redesign the homepage, update the buttons, and change the features. Your app gets better, **but the AI forgets to update the old test files.** When GitHub runs **Unit &amp; Component Tests**, the test looks for the old button, doesn't find it, and fails. Here, the test is wrong, not your app. You should either tell your AI to update the tests to match your current app, or remove outdated placeholder tests.
- **Production Standalone Build (Critical — Never Ignore):** Right now, this step says **Skipped** only because the first two steps failed. However, the Production Build is the single most important check in the pipeline. Running an app on your own computer (`npm run dev`) is very forgiving, whereas compiling an app for the real internet (`npm run build`) is strict. Furthermore, GitHub's cloud computer doesn't have the hidden local files on your machine (like your `.env` secret keys or unpushed local files). If the build step fails, your app **cannot be deployed** to platforms like Vercel, Netlify, or a VPS.

When deciding how to handle a GitHub Actions failure on an AI-built project, weigh these four factors:

1. **"Works on My Machine" vs. Clean Cloud Environment:** Your computer has cached packages, local `.env` files with API keys, and a forgiving development server. GitHub Actions tests whether your repository contains everything needed to build from scratch on a brand-new server. If a failure is caused by a missing `.env` variable or an uncommitted file, that is a crucial catch you need to fix before deploying.
2. **Stage of Your Project (Prototype vs. Production):** If you are rapidly prototyping and changing the UI every hour with AI, maintaining strict unit tests on every button will slow you down. At the prototype stage, it is completely normal to simplify your CI pipeline so it **only** checks Type Integrity and the Production Build, skipping Unit Tests until your core features stabilize.
3. **AI Context Drift (Using CI as Guardrails for AI):** Because you rely on AI to write the code, GitHub Actions is actually **more useful to you than to a traditional coder.** When you ask an AI to add Feature B, it might accidentally break Feature A without telling you. Automated checks act as a safety net that catches when the AI hallucinates a bad import or breaks an existing page.
4. **Effort to Fix with AI:** Because GitHub Actions gives you exact line numbers and error messages in the logs, you don't need to know how to fix them manually. You can copy the red error log from GitHub Actions, paste it directly into your AI coding tool, and let the AI resolve the issue in seconds.

---

### Interactive Pipeline Explorer

To see how these pieces fit together, step through the interactive pipeline below. It breaks down what happens behind the scenes during each stage of your **Phantom Labs** workflow, why AI-generated code typically trips each check, and whether you should enforce or relax that stage.

---

The healthiest habit you can build right now is to **open the failed run in the Actions tab, copy the red error text from both failed jobs, and paste it to your AI assistant.** Ask the AI whether the error is a real code/type issue that needs fixing or just an outdated test file that should be updated or removed. Once you do that once or twice, your pipeline will turn green—and from then on, any future email you get from GitHub will be a genuine heads-up that your latest AI prompt accidentally broke something important.

What would you like to do next with your pipeline?

## 👤 You

Alright Can you give me a guide to a pro level, Industry standard github configuration and workflow as I will be developing various types of apps and I do want them to be tested but I also want to be smart about it and leverage github actions properly to my advantage. This guide should contain all the essential things I need to be able to create professional level apps and leverage Github 

## 🤖 Assistant

Running a professional GitHub setup—especially when developing with AI—comes down to one core principle: **never push untested code directly to your `main` branch.** In an industry-standard workflow, `main` represents production-ready software that can be deployed at any moment.

By putting a lightweight "gatekeeper" process in front of `main`, you give yourself the freedom to let AI experiment, refactor, and build rapidly on side branches while GitHub Actions automatically verifies that nothing is broken before those changes touch your real app.

---

## 1\. The Industry-Standard Branching Workflow (GitHub Flow)

Professional teams and solo founders alike use **GitHub Flow** because it is fast, clean, and works across web apps, APIs, and automation tools. Instead of uploading files or pushing directly to `main`, you work in isolated loops:

1. **Create a Feature Branch:** Whenever you want your AI coding tool to build a new feature or fix a bug, create a new branch off `main` (for example, `feat/user-auth` or `fix/navbar-layout`).
2. **Develop &amp; Commit with AI:** Let your AI write code and make commits on that branch. If the AI breaks something while experimenting, your `main` branch remains untouched.
3. **Open a Pull Request (PR):** Push your feature branch to GitHub and open a Pull Request to merge it into `main`. Opening a PR automatically triggers **GitHub Actions**.
4. **Let CI Validate the PR:** GitHub Actions runs your automated checks on the PR. If a check fails, copy the error log back to your AI and push the fix to the same branch.
5. **Squash and Merge:** Once all checks turn green, click **Squash and merge** on the PR. This combines all the messy experimental AI commits into a single, clean commit on `main` and automatically deletes the temporary branch.

---

## 2\. Smart Testing Tiers: Matching CI to Your App's Stage

Testing everything at 100% strictness from Day 1 will slow you down, especially when AI is rapidly changing your UI. Smart engineering teams scale their GitHub Actions checks based on the maturity of the app:

| App Stage | What to Enforce in GitHub Actions | What to Skip / Make Optional | Why This Balance Works |
| --- | --- | --- | --- |
| **Stage 1: Prototype / MVP** | **Type Integrity (`tsc`)** &amp; **Production Build (`build`)** | Unit tests, UI component tests, strict formatting rules | Verifies the AI didn't hallucinate bad imports or break deployment, without forcing you to rewrite tests every time you change a button. |
| **Stage 2: Production / Client App** | **Linting**, **Type Integrity**, **Production Build**, &amp; **Core API/Logic Unit Tests** | Brittle visual snapshot tests | Protects business logic, calculations, and data flows while ensuring the app compiles cleanly. |
| **Stage 3: Mission-Critical / SaaS** | All of Stage 2 + **End-to-End (E2E) Playwright Tests** &amp; **Security Audits** | None | Simulates a real browser logging in and completing critical actions (like checkout or onboarding) before any code goes live. |

---

## 3\. Essential Repository Configuration (Step-by-Step Setup)

To turn any new repository into a pro-grade environment, configure these four built-in GitHub settings right after creating the repo:

### Step 1: Set Up a `main` Branch Ruleset (Branch Protection)

GitHub **Rulesets** prevent accidental pushes directly to `main` and force code to pass your CI checks before merging.

1. Go to your repository on GitHub and click **Settings** -&gt; **Rules** -&gt; **Rulesets** in the left sidebar.
2. Click **New ruleset** -&gt; **New branch ruleset**.
3. Name the ruleset `Protect Main`, set **Enforcement status** to **Active**, and under **Target branches**, click **Add target** -&gt; **Include default branch**.
4. Check the following boxes under **Branch rules**:
   
   - **Restrict deletions** (prevents accidental deletion of `main`).
   - **Require a pull request before merging** (set required approvals to `0` if you are working solo, or `1` if working with a team).
   - **Require status checks to pass** -&gt; click **Add checks** and select your GitHub Actions job names (such as `Build & Typecheck`).
   - **Block force pushes** (protects your commit history from being overwritten).
5. Click **Create** at the bottom.

### Step 2: Configure Secrets and Environment Variables

AI-built apps almost always rely on local `.env` files (API keys, database URLs) that are excluded from GitHub via `.gitignore` for security. When GitHub Actions builds your app, it needs those variables or it will fail.

1. Go to **Settings** -&gt; **Secrets and variables** -&gt; **Actions**.
2. Put sensitive keys (like `OPENAI_API_KEY` or `SUPABASE_SERVICE_ROLE_KEY`) under the **Secrets** tab.
3. Put non-sensitive configuration (like `NEXT_PUBLIC_APP_URL`) under the **Variables** tab.

### Step 3: Enable Clean Merging &amp; Auto-Cleanup

Keep your repository tidy so old branches don't pile up:

1. Go to **Settings** -&gt; **General** and scroll down to **Pull Requests**.
2. Check **Allow squash merging** (this keeps your `main` history clean even if you made 20 small "fix typo" commits with AI).
3. Check **Automatically delete head branches** (automatically deletes feature branches after you merge a PR).

### Step 4: Turn On Dependabot for Automated Security

1. Go to **Settings** -&gt; **Code security** (or **Advanced Security**).
2. Enable **Dependabot alerts** and **Dependabot security updates**. GitHub will automatically scan your libraries for known vulnerabilities and open a Pull Request for you whenever a security patch is needed.

---

## 4\. The "Pro-Smart" GitHub Actions Workflow Template

Instead of running three separate, noisy jobs that waste your GitHub Actions minutes and send multiple failure emails, use a single, fast, cached workflow file (`.github/workflows/ci.yml`).

This industry-standard template includes three pro optimizations:

- **Concurrency Cancellation:** If you push twice in 30 seconds, it automatically cancels the older run to save compute minutes.
- **Dependency Caching:** Caches `node_modules`/npm packages so runs take 30–45 seconds instead of 3 minutes.
- **Smart Ordering:** Runs fast checks (Types/Lint) first, tests second, and the Production Build last.

```yaml
name: Smart CI Pipeline

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

# Pro optimization: Cancel in-progress runs if a new commit is pushed to the same branch
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  validate-and-build:
    name: Validate, Test & Build
    runs-on: ubuntu-latest

    steps:
      - name: 1. Checkout Repository
        uses: actions/checkout@v4

      - name: 2. Setup Node.js with Dependency Caching
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'

      - name: 3. Install Dependencies Cleanly
        run: npm ci

      - name: 4. Type Integrity Check
        # Catches hallucinated AI imports and broken TypeScript types fast
        run: npx tsc --noEmit

      - name: 5. Linter (Non-Blocking Warning Mode for Prototypes)
        # Remove 'continue-on-error: true' when you want strict lint enforcement
        continue-on-error: true
        run: npm run lint --if-present

      - name: 6. Unit Tests (Runs if present)
        # To skip stale tests during early prototyping, comment out this step
        run: npm test -- --watchAll=false --passWithNoTests

      - name: 7. Production Build Verification
        # Ensures the app can actually compile and deploy to production
        run: npm run build
```

---

## 5\. Repo Hygiene Files That Supercharge AI Development

Adding three small files to your repository makes both GitHub and your AI coding tools work significantly better:

- **`.gitignore`:** Ensures `node_modules/`, `.env`, `.env.local`, and build folders (`dist/`, `.next/`) are never uploaded to GitHub. (Uploading `node_modules` by accident is one of the top reasons GitHub Actions breaks on new uploads).
- **`.github/pull_request_template.md`:** A short markdown checklist that auto-populates whenever you open a PR (e.g., *"- \[ \] Verified `.env.example` is updated"*).
- **`AGENTS.md` / `CLAUDE.md` / `.cursorrules`:** Add a rule at the top of your AI instruction file stating:
  
  > *"Before finishing any task, always run `npx tsc --noEmit` and `npm run build` locally to verify that TypeScript types and the production build succeed, and update or remove any affected unit tests."*
  > This single instruction prevents 90% of GitHub Actions failures before the code ever leaves your computer.

---

### Interactive Pro GitHub Workflow Explorer

Click through the interactive diagram below to see how code moves from your AI assistant through a feature branch, Pull Request, smart CI checks, and branch protection gates into production—and use the mode toggle to compare this against pushing directly to `main`.

---

Would you like to tailor that `ci.yml` workflow specifically to the framework you're using for **Phantom-Labs-Webapp** (such as Next.js, Vite/React, or Node), or walk through converting your current failing workflow into this streamlined version?

## 👤 You

How do I set up a Staging preview environment alongside Production using GitHub branches?

## 🤖 Assistant

Setting up a **Staging** environment alongside **Production** gives you a live, private rehearsal site (like `staging.yourdomain.com`) where you can test your AI-built features with real cloud servers and APIs before your actual users ever see them.

In an industry-standard GitHub setup, your **Git branches** control which environment gets updated:

- **`feat/*` (Feature Branches) -&gt; Temporary Preview URLs:** Used while prompting your AI to build a feature.
- **`staging` Branch -&gt; Staging Environment (`staging.yourdomain.com`):** Your persistent testing server where new features are combined and tested together.
- **`main` Branch -&gt; Production Environment (`yourdomain.com`):** Your live, public-facing app.

---

## Step 1: Create and Protect Your `staging` Branch on GitHub

First, create a permanent `staging` branch in your repository so code flows in a strict order: **`feature branch` -&gt; `staging` -&gt; `main`**.

---

## Step 2: Separate Your Staging and Production Secrets (Crucial)

Never connect your Staging website to your live Production database or live Stripe payment keys—otherwise, testing a "Delete User" button on Staging will delete real customer data. GitHub has a built-in feature called **Environments** specifically for this.

---

## Step 3: Connect Your Hosting Platform to Your Branches

How you deploy the actual websites depends on where you host your apps. Below are the two industry-standard setups.

### Approach A: Managed Cloud Hosting (Vercel, Netlify, Cloudflare Pages)

If you host web apps on a platform like Vercel or Netlify, you don't even need to write deployment scripts—they natively watch your GitHub branches:

1. **Import Your GitHub Repo:** Connect your repository to Vercel/Netlify. By default, it sets `main` as your **Production Branch** (`yourdomain.com`).
2. **Assign the Staging Domain:** In your hosting dashboard, go to **Settings** -&gt; **Domains**, add `staging.yourdomain.com`, and assign it to track the **`staging` Git branch**.
3. **Scope Your Environment Variables:** In your hosting dashboard's **Environment Variables** settings, check the **Production** box for your live keys, and check the **Preview / Staging** box for your test keys.
4. **Automatic PR Previews:** Every time you open a Pull Request on GitHub, the host will automatically reply to your PR with a unique temporary link so you can test the AI's changes in your browser before merging into `staging`.

### Approach B: Deploying to Your Own VPS or Cloud Server via GitHub Actions

If you deploy apps to your own VPS or custom cloud server, you can update your `.github/workflows/ci.yml` file so it runs your tests on every branch, and then deploys to either Staging or Production depending on which branch was updated:

```yaml
name: CI & Multi-Environment Deploy

on:
  push:
    branches: [staging, main]
  pull_request:
    branches: [staging, main]

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  validate-and-build:
    name: 1. Validate, Test & Build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
      - run: npm ci
      - run: npx tsc --noEmit
      - run: npm test -- --watchAll=false --passWithNoTests
      - run: npm run build

  deploy-staging:
    name: 2A. Deploy to Staging
    needs: validate-and-build
    # Only runs when code is pushed/merged into the 'staging' branch
    if: github.event_name == 'push' && github.ref == 'refs/heads/staging'
    runs-on: ubuntu-latest
    environment:
      name: staging
      url: https://staging.yourdomain.com
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to Staging Server
        env:
          SERVER_SSH_KEY: ${{ secrets.VPS_SSH_KEY }}
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
        run: |
          echo "Deploying to Staging environment using Staging secrets..."
          # Add your VPS SSH / Docker / rsync deployment command here

  deploy-production:
    name: 2B. Deploy to Production
    needs: validate-and-build
    # Only runs when code is pushed/merged into the 'main' branch
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment:
      name: production
      url: https://yourdomain.com
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to Production Server
        env:
          SERVER_SSH_KEY: ${{ secrets.VPS_SSH_KEY }}
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
        run: |
          echo "Deploying to Production environment using Production secrets..."
          # Add your Production deployment command here
```

---

## Step 4: Your Daily "Feature -&gt; Staging -&gt; Production" Routine

Once this is set up, promoting AI-built features from your computer to your live users follows a predictable, stress-free cycle:

1. **Build on a Feature Branch:** Branch off `staging` (e.g., `feat/ai-chatbot`), build the feature with your AI assistant, and open a Pull Request targeting **`staging`**.
2. **Merge to `staging`:** Once GitHub Actions turns green, merge the PR into `staging`. Your **Staging site (`staging.yourdomain.com`)** updates automatically within a minute.
3. **Test on Staging:** Click around `staging.yourdomain.com` on your phone and desktop to make sure the feature works with real cloud APIs.
4. **Promote to `main` (Production):** When you are happy with Staging, open a Pull Request on GitHub with **base: `main`** and **compare: `staging`**, and click **Merge** (keep regular **Create a merge commit** selected when promoting `staging` to `main` so both branches stay in sync). Your live production site updates immediately.

---

### Interactive Multi-Environment Branching Explorer

Step through the interactive diagram below to see how commits move across `feature`, `staging`, and `main` branches, and inspect which environment URL and secret keys get triggered at each stage.

## 👤 You

I have my own VPS. Show me how to set up GitHub Actions to automatically deploy my staging and main branches to my VPS over SSH.

## 🤖 Assistant

Deploying both **Staging** and **Production** to a single VPS over SSH works by running two isolated copies of your app on the same server—each in its own folder, running on its own local port, with a Reverse Proxy (like Nginx or Caddy) routing traffic based on the domain name.

| Environment | Git Branch | Folder on Your VPS | Local Port | Process Name / Container | Public Domain |
| --- | --- | --- | --- | --- | --- |
| **Staging** | `staging` | `/var/www/app-staging` | `localhost:3001` | `app-staging` | `staging.yourdomain.com` |
| **Production** | `main` | `/var/www/app-prod` | `localhost:3000` | `app-prod` | `yourdomain.com` |

> **Why Build on GitHub First?** Never make a lightweight VPS compile heavy TypeScript/Next.js/React builds while it is serving live user traffic—that spikes your VPS CPU to 100% and can crash your live site. Instead, let **GitHub Actions' free cloud servers** do the heavy testing and building, or use Docker/PM2 cleanly over SSH.

---

## Complete Setup Guide: VPS + GitHub Actions SSH

Follow these steps in order to prepare your VPS, authorize GitHub Actions, and configure the automated deployment pipeline.

---

## Pro VPS Security &amp; Reliability Tips

- **Use `git reset --hard origin/<branch>` Instead of `git pull`:** In the deployment script above, `git fetch` followed by `git reset --hard` guarantees the VPS never gets stuck with a merge conflict if `package-lock.json` was slightly modified on the server. Because `.env` is in your `.gitignore`, `git reset --hard` will **not** touch or delete your server's `.env` file.
- **Lock Staging Behind a Password (Optional):** If you don't want search engines or competitors indexing `staging.yourdomain.com`, add HTTP Basic Auth in Nginx (`auth_basic "Staging Area";`) so a browser password prompt appears when visiting the Staging URL.
- **Add a 1-Click Approval Gate for Production:** In your GitHub repo under **Settings** -&gt; **Environments** -&gt; **`production`**, check **Required reviewers** and add your own GitHub username. Whenever you merge to `main`, GitHub will pause the `deploy-production` job and send you a notification so you can click **Approve and deploy** when you are ready for the VPS to update.

## 👤 You

Create a template for an AI agent that can manage github for me with all the above mentioned functionality.

## 🤖 Assistant

To turn your AI coding assistant (Cursor, Claude Code, Windsurf, GitHub Copilot, or a custom agent) into an autonomous **GitHub &amp; DevOps Manager**, you need two things:

1. **GitHub CLI (`gh`) installed and logged in** on your computer (run `gh auth login` once in your terminal—this gives your AI agent full ability to create branches, open Pull Requests, read failed GitHub Actions logs, set secrets, and configure branch rulesets).
2. **A master `AGENTS.md` instruction file** placed in the root folder of your project (you can also save it as `.cursorrules` or `CLAUDE.md`).

---

## 1\. The Master Agent Instruction Template (`AGENTS.md`)

Create a file named **`AGENTS.md`** in the root folder of your repository and paste the template below. Any modern AI coding agent reading your repo will automatically follow these exact workflows, pre-flight checks, CI self-healing steps, and VPS deployment architectures.

````markdown
# Role: Autonomous GitHub, CI/CD & VPS Release Manager

You are the Lead DevOps & GitHub Release Agent for this repository. Beyond writing application code, you are strictly responsible for maintaining Git hygiene, running pre-flight verification checks, managing branches (`feat/*` -> `staging` -> `main`), diagnosing GitHub Actions failures, and maintaining our VPS deployment pipeline.

---

## 1. Core Git & Branching Rules (Strict Enforcement)

1. **NEVER commit or push directly to `main` or `staging`.**
   - `main` is strictly reserved for Production releases.
   - `staging` is strictly reserved for Staging integration and rehearsal.
2. **Branch Naming Convention:**
   - Before writing code for any new feature, fix, or refactor, verify the current branch with `git branch --show-current`.
   - Always branch off `staging` (`git checkout staging && git pull origin staging && git checkout -b <branch-name>`).
   - Use prefixes: `feat/<short-name>`, `fix/<short-name>`, `chore/<short-name>`, or `ci/<short-name>`.
3. **Repository Hygiene:**
   - Never stage or commit `.env`, `.env.local`, `node_modules/`, `.next/`, `dist/`, or private SSH keys.
   - Whenever you add a new environment variable to the codebase, immediately add a placeholder entry to `.env.example` and alert the user so it can be added to GitHub Environments and the VPS.

---

## 2. Mandatory Pre-Flight Checklist (Run Before Every Push)

Before pushing any branch to GitHub or telling the user a task is complete, you MUST run the following local verification sequence in the terminal and fix all errors until every command exits with code `0`:

1. **Type Integrity Check:**
   ```bash
   npx tsc --noEmit
````

*Rule:* Do not leave unused imports, implicit `any` types, or mismatched component props.
2\. **Linter Check:**

```bash
npm run lint --if-present
```

3. **Unit &amp; Component Test Sync:**
   
   ```bash
   npm test -- --watchAll=false --passWithNoTests
   ```
   
   *Rule on Stale AI Tests:* If you modified UI components, text, or business logic, inspect existing test files (`*.test.ts`, `*.test.tsx`, `*.spec.ts`). Update outdated placeholder tests to reflect the new implementation rather than letting CI fail on stale assertions.
4. **Production Build Verification:**
   
   ```bash
   npm run build
   ```
   
   *Rule:* Verify that the production bundle compiles cleanly with zero missing dependencies or case-sensitive file import errors.

---

## 3\. Pull Request &amp; Promotion Workflow (Using GitHub CLI `gh`)

Once the Pre-Flight Checklist passes locally, manage the release lifecycle using the GitHub CLI (`gh`):

### Flow A: Submitting a Feature or Fix to Staging

1. Stage and commit changes using conventional commit messages (`feat: ...`, `fix: ...`, `chore: ...`).
2. Push the branch: `git push -u origin HEAD`
3. Open a Pull Request targeting `staging`:
   
   ```bash
   gh pr create --base staging --head "$(git branch --show-current)" --title "<Title>" --body "<Summary and changes of steps verification>"
   ```
4. Monitor the GitHub Actions CI run automatically:
   
   ```bash
   gh pr checks --watch
   ```
5. Once checks pass and the user approves, squash-merge into `staging` and delete the branch:
   
   ```bash
   gh pr merge --squash --delete-branch
   ```

### Flow B: Promoting `staging` to `main` (Production Release)

When the user asks to "Promote to Production" or "Release to Main":

1. Open a promotion PR from `staging` to `main`:
   
   ```bash
   gh pr create --base main --head staging --title "Release: Promote Staging to Production" --body "Automated promotion of verified staging build to production."
   ```
2. Watch CI checks (`gh pr checks --watch`).
3. Merge using a standard **merge commit** (NEVER squash-merge `staging` into `main`, so both branch histories stay synchronized):
   
   ```bash
   gh pr merge --merge
   ```

---

## 4\. Autonomous CI Failure Diagnosis &amp; Self-Healing Protocol

When the user says **"Fix CI"** or when `gh pr checks` reports a failure:

1. Find the latest failed run ID:
   
   ```bash
   gh run list --limit 5
   ```
2. Fetch the exact failure logs directly into your context:
   
   ```bash
   gh run view <RUN_ID> --log-failed
   ```
3. Classify and fix the root cause:
   
   - **Type/Lint Error:** Fix the offending file and line number reported in the log.
   - **Stale Test Failure:** Update the test assertion to match current intentional app behavior, or fix the broken function if a real regression occurred.
   - **Missing Secret / Env Variable:** Check if the build failed due to an undefined environment variable, and prompt the user to set it via `gh secret set <NAME> --env staging` or `production`.
4. Commit the fix, push to the branch, and re-verify with `gh run watch`.

---

## 5\. Standard CI/CD &amp; VPS SSH Architecture Reference

When asked to initialize or repair `.github/workflows/ci.yml` for this repository, maintain this architecture:

- **Concurrency:** Always enable `cancel-in-progress: true` grouped by `${{ github.workflow }}-${{ github.ref }}`.
- **Caching:** Use `actions/setup-node@v4` with `cache: 'npm'` and `npm ci`.
- **Multi-Environment VPS Deployment (`appleboy/ssh-action`):**
  
  - Push to `staging` -&gt; Deploys to `/var/www/app-staging` on port `3001` via PM2 (`app-staging`) using the `staging` GitHub Environment.
  - Push to `main` -&gt; Deploys to `/var/www/app-prod` on port `3000` via PM2 (`app-prod`) using the `production` GitHub Environment.
  - Always use `git fetch origin <branch> && git reset --hard origin/<branch>` on the VPS to prevent lockfile merge conflicts while preserving the server's untracked `.env` file.

```

---

## 2. One-Command Repository Bootstrap Prompt

Whenever you create a brand-new app and want your AI agent to set up all of your branches, workflows, and GitHub settings automatically, paste this exact prompt to your AI:

> *"Read `AGENTS.md` and initialize our standard GitHub & VPS workflow for this repository:*
> 1. *Ensure `.gitignore` excludes `node_modules`, `.env*` (except `.env.example`), and build output folders.*
> 2. *Create `.github/workflows/ci.yml` with our cached Validate/Test/Build job and conditional SSH deployment jobs for `staging` (port 3001) and `main` (port 3000).*
> 3. *Run our Pre-Flight Checklist (`tsc`, `lint`, `test`, `build`) and fix any initial issues so the project builds cleanly.*
> 4. *Using `gh`, create the `staging` branch, push both `main` and `staging` to GitHub, and tell me which repository secrets I need to set for the VPS."*

---

## 3. Cheat Sheet: How to Command Your Agent Day-to-Day

Once `AGENTS.md` is in your project folder, you no longer have to remember Git commands or click around GitHub Actions logs. You can manage your entire development cycle with five natural-language commands:

| What You Want to Do | What to Say to Your AI Agent | What the Agent Will Automatically Do |
| :--- | :--- | :--- |
| **Start a New Feature** | *"Start a new feature for user login and build the UI."* | Checks out `staging`, creates branch `feat/user-login`, writes the code, and updates `.env.example` if needed. |
| **Ship to Staging** | *"Run pre-flight checks and ship this to Staging."* | Runs `tsc`, `lint`, `test`, and `build` locally, fixes any errors, pushes the branch, opens a PR to `staging`, watches GitHub Actions turn green, and merges it. |
| **Fix a Red GitHub Email** | *"Check the latest failed GitHub Action and fix it."* | Runs `gh run view --log-failed`, reads the exact error log from GitHub, fixes the broken types or stale tests, and pushes the fix. |
| **Add a Secret Key** | *"Add `STRIPE_KEY` to my GitHub staging environment."* | Runs `gh secret set STRIPE_KEY --env staging` so your pipeline has the key without exposing it in code. |
| **Release to Production** | *"Staging looks great. Promote Staging to Production."* | Opens a PR from `staging` -> `main`, verifies all status checks pass, merges it cleanly, and triggers your live VPS deployment. |

<ElicitationsGroup message="How would you like to put this agent template into action?">
  <Elicitation label="Install and connect GitHub CLI (gh)" query="Walk me through installing the GitHub CLI (gh) and authenticating it so my AI coding agent can run gh commands for me."/>
  <Elicitation label="Auto-configure GitHub Rulesets via CLI" query="Give me a bash script my AI agent can run using the GitHub CLI (gh api) to automatically create the main and staging branch protection rulesets."/>
  <Elicitation label="Clean up Phantom-Labs-Webapp now" query="Give me a tailored prompt I can paste into my AI editor right now to fix the current CI failures in Phantom-Labs-Webapp and set up this workflow."/>
</ElicitationsGroup>
```
