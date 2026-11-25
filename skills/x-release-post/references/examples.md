# tokenjuice release posts on X

Source posts by [@vincent_koc](https://x.com/vincent_koc), quoted verbatim, with
shortened links replaced by their targets. Metrics were read from the X API on
2026-11-23; dates are UTC. Eight posts are a small sample, so treat the
performance notes as signals, not rules.

| Post | Date | Likes | Views | Bookmarks | Weighted length |
|---|---|---|---|---|---|
| [Teaser](https://x.com/vincent_koc/status/2044168725016768734) | 2026-04-14 | 48 | 2,767 | 4 | 257 |
| [v0.2 beta](https://x.com/vincent_koc/status/2044821621773623331) | 2026-04-16 | 96 | 14,325 | 73 | 278 |
| [v0.2 install reply](https://x.com/vincent_koc/status/2044821623711412251) | 2026-04-16 | 7 | 1,061 | 5 | 222 |
| [v0.4 beta](https://x.com/vincent_koc/status/2045518362902729134) | 2026-04-18 | 65 | 20,482 | 65 | 245 |
| [v0.6.1](https://x.com/vincent_koc/status/2046968242280051090) | 2026-04-22 | 72 | 8,819 | 29 | 257 |
| [100k installs](https://x.com/vincent_koc/status/2047346212710596686) | 2026-04-23 | 78 | 3,942 | 10 | 49 |
| [v0.6.3](https://x.com/vincent_koc/status/2048260059256521035) | 2026-04-26 | 67 | 5,467 | 37 | 277 |
| [v0.8.0](https://x.com/vincent_koc/status/2059049567643959469) | 2026-05-25 | 23 | 3,059 | 12 | 276 |
| [2.5M npm downloads](https://x.com/vincent_koc/status/2060758429354934775) | 2026-05-30 | 226 | 15,569 | 100 | 277 |

Weighted length is the `scripts/x-post-length` result with attached-image links
removed. Most version posts use 245-278 of the 280 characters.

## What the sample shows

- The milestone post with a personal angle (project age, licence, reach) and a
  chart image has the most likes and bookmarks.
- The v0.2 post opens with a one-line metaphor and has the most likes of the
  version posts. Its install reply got few likes; it serves readers who click
  through, not reach.
- The v0.4 post has the most views. It has five short emoji bullets and no
  mentions.
- The v0.8.0 post replaces bullets with a long comma-separated list of
  integrations and has the fewest likes and views.

## Version post: v0.2 beta

```text
tokenjuice beta (v0.2) is out! 🧃

💉 Ozempic for your shell toolcalling
💻 Native codex intergration hooks
👏 5-30% less tokens with git, npm, etc
🤖 Powered by regex, mega fast
📄 Simple json based config, MIT licenced
🦞 @openclaw coming soon

 Get it https://github.com/vincentkoc/tokenjuice
```

Reply in the same thread, with a screenshot:

```text
Essentially we wrap toolcalling around a smart regex engine with rules that can diet your tokens heading to your LLM or harness.

Run:
- brew tap vincentkoc/homebrew-tap
- brew install tokenjuice
- tokenjuice install codex
```

## Version post across releases: 0.4 to 0.6.1

```text
tokenjuice new version out (0.4->0.6.1):

🦞 Nativley bundled in next @openclaw release
🤖 @cursor_ai IDE intergration
🪟 Improvements to Windows users
🔧 Better doctor and stats
👏 More compaction rules

Lets cold press some tokens! https://github.com/vincentkoc/tokenjuice/
```

## Version post with grouped mentions: v0.6.3

```text
tokenjuice 🧃(v0.6.3) released!

🥳 New @zeddotdev @continuedev @cline @OpenHandsDev and more
🚸 Codex no longer reporting false errors
⚙️ Better bypass and rules
🕐 Timezone and stats improvements

Give your llm's some juice and reduce your tool tokens https://github.com/vincentkoc/tokenjuice/releases/tag/v0.6.3
```

## Milestone post: 2.5M downloads

```text
🥳 My 6 week old side project just surpassed 2.5mill downloads on npm.

🧃TokenJuice was started as a concept to help reduce token use with tools, as a TypeScript SDK and in an MIT licence for all. It now supports close to 100 different coding IDEs and harnesses.

Crazy stuff!
```

Posted with a chart image of npm downloads.

## Weakest version post: v0.8.0

```text
tokenjuice v0.8.0 is out 🧃

the funny number: 99 intergrations supported

Codex, Claude Code, Cursor, OpenCode, Copilot, Gemini CLI, Qwen Code, Cline, Devin, OpenHands, and a genuinley stupid ammount more.

less terminal sluge for your agents to read

https://github.com/vincentkoc/tokenjuice
```

The number is a good hook. A rewrite would keep it in the first line, put the
names in one grouped @-mention line, and add two or three bullets for what else
changed.
