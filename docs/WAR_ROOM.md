# AXIOM War Room

War Room turns a completed Survival Lab experiment into three review
perspectives: Challenger, Defender and Auditor. Each perspective refers to
evidence from that synthetic experiment; evidence cards with **Inspect in
replay** open the corresponding candle and recorded path.

## Try the offline walkthrough

1. Start the local demo from the project root:

   ```bash
   source venv/bin/activate
   python scripts/demo.py
   ```

2. Open the printed URL. Under **Explore demo credentials**, select **Admin**
   and then **Enter workspace**.
3. In Survival Lab, select **Run the experiment**. Choose **Enter the War
   Room** and select **Open the review**.
4. Select an evidence reference in a perspective, then **Inspect in replay**
   when available. The replay opens the appropriate guarded or unguarded
   path. If the controls change, the review stays tied to the last completed
   run; running an experiment with different settings starts a new case.
5. Choose a human review outcome, optionally add a note, and select **Download
   case file** to keep the review and its evidence references as JSON. Notes
   are not sent to the model or saved to the server. Re-reviewing the same
   case keeps them in the browser; a different case replaces them.

The offline walkthrough uses deterministic rules and the simulation results;
it does **not** call an AI model. It does not require internet access after
installation. A reference identifies an item in the run; it is not an
independent audit or proof that a claim is true.
The case file is also not signed or independently verified; the Survival Lab
passport contains the fuller simulation record.

## Optional Claude perspectives

The model-backed option requires an Anthropic API key in the backend's
environment. A Claude Code login or subscription is separate from an API key
for an application. On macOS with zsh, from the project root:

```zsh
source venv/bin/activate
read -rs 'AXIOM_ANTHROPIC_API_KEY?Anthropic API key: '
export AXIOM_ANTHROPIC_API_KEY
python scripts/demo.py
```

The key is not displayed by `read` or placed in the command itself. Keep it
out of source files, screenshots and Git. Restart the server after changing
the key. You can optionally set `AXIOM_ANTHROPIC_MODEL` before starting the
demo; otherwise the configured default is used.

Select **Claude perspectives** and **Open the review** to make three
requests to Anthropic. This sends the generated synthetic scenario evidence
and incurs API usage charges according to the configured account. The first
two perspectives independently see the same evidence, while the auditor also
sees their responses; all three use the same configured model. They have no
trading, retrieval or browser tools. Errors are surfaced rather than replaced
with an AI-looking scripted answer.

As a local guardrail, each backend process permits five Claude review attempts
per launch. A failed attempt still counts because some provider calls may have
been billed. Restarting resets this counter; multiple server processes each
have their own counter. It is not a persistent, account-wide or monetary
spending limit, and this demo is not designed for public deployment. The
offline walkthrough is not limited by this counter.

The model's words may be wrong even when the cited identifier exists. Do not
treat agreement, a citation, or the display as independent verification.
This prototype is not financial advice and cannot place real orders.

For the research behind these choices and a proposed evaluation, see
[War Room research](WAR_ROOM_RESEARCH.md).
