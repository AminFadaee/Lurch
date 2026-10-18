# Lurch

Build your own Anki vocabulary deck from a list of English words. Every card is one *meaning* of a word, not
the word itself, so words like *constitution* get a card for each meaning. Each card has a plain definition,
synonyms or related words, an example sentence, and a spoken word and sentence.

Everything is built from open data, and the word list is a plain text file, so anyone can make a deck of their own.

## Quick start

Requires [uv](https://docs.astral.sh/uv/).

```sh
uv sync
cp words.example.txt words.txt
uv run lurch build
```

Edit `words.txt` first: one word per line, `#` starts a comment. The deck is written to
`build/lurch_vocabulary.apkg`; open it in Anki (File → Import).

`words.txt`, `data/` and `build/` are git-ignored, so your list and your deck stay on your machine.

The first run downloads about 5 GB of models and data (WordNet, GloVe vectors, the Tatoeba sentences, the
embedding and reranking models, and the Kokoro voice model) and takes a few minutes. Later runs reuse them.

## Configuration

Copy `.env.example` to `.env` to change a setting.

| Variable | Default | Meaning |
|---|---|---|
| `LURCH_VOICES` | eight US Kokoro voices | comma-separated [Kokoro voices](https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md); each word and sentence is read by one of them, chosen from a hash of its text |
| `LURCH_DECK_NAME` | `Lurch Vocabulary` | name of the deck and the output file |
| `LURCH_WORDS` | `words.txt` | the word list; `--words PATH` overrides it |

## The cards

Each meaning becomes one note with three cards:

| Card | Front | Back |
|---|---|---|
| Recognition | the word, read aloud, and its example sentence | the definition, synonyms, related words and the word's other meanings |
| Recall | the definition, its synonyms and the sentence with the word blanked; you type the word | your spelling checked, the word and the full sentence read aloud |
| Listening | the word read aloud, a button for the sentence as a hint; you type the word | your spelling checked, with the full meaning |

When a word has several meanings, a small cue on the card says which one it is, and the back lists the others.

## How it works

`uv run lurch build` runs four steps; each can also be run alone (`senses`, `sentences`, `audio`, `deck`) and
reads the previous step's `data/entries.json`.

1. **Senses.** Looks each word up in Open English WordNet and keeps up to three of its most different common
   meanings. A definition that is built on the word itself (*pedagogical*: "of or relating to pedagogy") is
   replaced by the definition of its base word (*pedagogy*), or dropped when no base word is found.
   Synonyms and broader terms come from WordNet. When a meaning has fewer than two synonyms, related words
   from GloVe vectors are added, kept only if they are close in meaning.
2. **Sentences.** Picks example sentences from Tatoeba. Sentences that quote the word, define it or talk
   about language are skipped. For a word with several meanings a sentence is used only when a reranker is
   confident which meaning it shows; otherwise that meaning has no sentence.
3. **Audio.** Speaks the word and its sentence with Kokoro.
4. **Deck.** Writes the Anki package.

The log of what was changed (words folded into a base word, meanings dropped) is printed by the `senses` step.

## Limits

- A meaning without a confident sentence gets a card with no example.
- WordNet is the only source of meanings and synonyms, so very new or technical words may have none.
- Word-vector neighbours describe a word in general, not one meaning, so they are only used for words with a
  single meaning.

## Sources and licences

| Source | Used for | Licence |
|---|---|---|
| [Open English WordNet 2024](https://en-word.net/) | meanings, synonyms, broader terms | CC BY 4.0 |
| [Tatoeba](https://tatoeba.org/) | example sentences | CC BY 2.0 FR |
| [GloVe wiki-gigaword-100](https://nlp.stanford.edu/projects/glove/) | related words | PDDL |
| [wordfreq](https://github.com/rspeer/wordfreq) | word frequency | CC BY-SA 4.0 |
| [bge-base-en-v1.5](https://huggingface.co/BAAI/bge-base-en-v1.5), [bge-reranker-large](https://huggingface.co/BAAI/bge-reranker-large) | matching meanings and sentences | MIT |
| [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) | speech | Apache 2.0 |

A deck contains Tatoeba sentences, so share it with attribution to Tatoeba and its contributors.
