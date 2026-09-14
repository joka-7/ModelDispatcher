# AI glossary

Plain-language definitions for the terms every app's AI settings screen
throws at a new user. Linked from
[`ModelPicker`](../clients/react-ui)'s "New to AI agents?" link — this is the
page that link goes to.

## Model

The actual AI system that turns your text into a reply — Google's Gemini,
OpenAI's GPT, Anthropic's Claude, and so on. Different models cost different
amounts, answer at different speeds, and are better or worse at different
kinds of tasks. "Which model?" just means "which AI, specifically" — most
providers offer several, usually trading cost against capability.

## Provider

The company that runs a model and answers requests for it — Google,
OpenAI, Anthropic, Groq. "Provider" is the company/service; "model" is the
specific AI it's running for you.

## Prompt

The text you send the model — your question or instruction. Everything the
model produces is a response to some prompt, whether you typed it directly
or an app built it for you behind the scenes.

## Agent

A program that uses a model in a loop: it can look at the model's reply,
decide to take an action (like calling a tool or searching for something),
feed the result back in, and repeat — instead of a single one-shot
question and answer. "AI agent" just means "AI with the ability to act
and iterate," not a fundamentally different technology from the model
underneath it.

## API key

A password-like string that proves to a provider that requests are coming
from you, and lets them bill (or rate-limit) your usage specifically. You
get one from the provider's own website — see the "Get a key" link next to
each provider in the picker — and it goes in the app's settings, not shared
with anyone else. No API key is required to use the "try it free in another
app" option in `ModelPicker`: that hands your question to the provider's own
free public chat website instead of calling its API directly.

## BYOK (bring your own key)

The pattern this project's browser-based apps use: instead of the app
paying for and managing API keys on your behalf, you supply your own key for
whichever provider you want to use. The app never sees or stores your key
anywhere but your own browser.
