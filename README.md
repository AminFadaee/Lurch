# Lurch

Build your own Anki vocabulary deck from a list of English words. Every card is one *meaning* of a word, not
the word itself, so words like *constitution* get a card for each meaning. Each card has a plain definition,
synonyms or related words, an example sentence (more of them under "More examples"), and a spoken word and
sentence.

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

The first run downloads about 7 GB of models and data (WordNet, GloVe vectors, the Tatoeba sentences, four
language models for matching, filtering and reranking, and the Kokoro voice model) and takes a few minutes.
Later runs reuse them.

## Optional: local language models

Without any model the pipeline uses only open dictionary and corpus data, and a meaning that has no good
example sentence simply gets none. With [Ollama](https://ollama.com) you can add two models:

| Variable | Role |
|---|---|
| `LURCH_JUDGE_MODEL` | reviews the example sentences picked from the open data and vetoes bad ones (vague, garbled, wrong meaning, about language) |
| `LURCH_WRITER_MODEL` | writes example sentences only when no open-data sentence was accepted, and a definition only when every open-data definition is unusable |

I use `qwen3.5:4b` as the judge and `qwen3.5:9b` as the writer. Before it is used, the judge has to flag a
few planted bad sentences; if it does not, the run continues without models. Every model answer is cached in
`.cache/llm/`, so rerunning is cheap. A writer needs a judge.

## Configuration

Copy `.env.example` to `.env` to change a setting.

| Variable | Default | Meaning |
|---|---|---|
| `LURCH_VOICES` | eight US Kokoro voices | comma-separated [Kokoro voices](https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md); each word and sentence is read by one of them, chosen from a hash of its text |
| `LURCH_DECK_NAME` | `Lurch Vocabulary` | name of the deck and the output file |
| `LURCH_WORDS` | `words.txt` | the word list; `--words PATH` overrides it |
| `LURCH_JUDGE_MODEL`, `LURCH_WRITER_MODEL` | empty | Ollama models, see above |
| `LURCH_OLLAMA_URL` | `http://localhost:11434` | where Ollama runs |

## The cards

Each meaning becomes one note with two cards, styled like the [Ultimate Countries](https://github.com/AminFadaee/Ultimate-Countries)
deck (light and dark):

| Card | Front | Back |
|---|---|---|
| Meaning | the word, read aloud, its part of speech and its example sentence; you recall the meaning | the definition, the sentence read aloud, chips for synonyms, related words, opposites and the word's other forms, a collapsible list of more examples and the word's other meanings |
| Listening | the word read aloud, with a button for the sentence as a hint; you type the word | your spelling checked, with the part of speech, the definition and the same chips |

When a word has several meanings, a small cue after the part of speech (*noun · law*) says which one it is.

A note has seven fields (`Word`, `Subtitle`, `Definition`, `Sentence`, `Details`, `WordAudio`, `SentenceAudio`) and
none is ever empty: everything optional is gathered into `Details`.

## How it works

`uv run lurch build` runs four steps; each can also be run alone (`senses`, `sentences`, `audio`, `deck`) and
reads the previous step's `data/entries.json`.

1. **Senses.** Takes the meanings from the English Wiktionary, joins the matching definitions from Simple
   English Wiktionary and WordNet, and keeps the three best supported. A definition built on the word itself
   (*pedagogical*: "of or relating to pedagogy") is replaced by the base word's (*pedagogy*). Each meaning gets
   one definition, chosen by plain wording, length and agreement between the sources. Synonyms come from
   WordNet and from Wiktionary (only common words close in meaning); when there are fewer than two, broader
   terms and related words from GloVe vectors are added.
2. **Sentences.** Collects the examples attached to each meaning in the dictionaries and the Tatoeba sentences
   that a classifier confidently ties to a meaning. Sentences that quote the word, define it, talk about
   language, are explicit or are hard to read are dropped; the rest are ranked, and the judge model, if
   there is one, vetoes bad ones. If nothing is left, the writer model may write one. A meaning with no
   acceptable sentence is dropped, unless it is the word's only meaning.
3. **Audio.** Speaks the word and its main sentence with Kokoro.
4. **Deck.** Writes the Anki package.

The `senses` and `sentences` steps print what they changed: words folded into a base word, meanings dropped,
sentences missing.

## Limits

- The choices between near-equal definitions and sentences come from rules tuned on a handful of words, so
  expect some picks you would change.
- Sentences written by a model are generic ("a clandestine meeting behind locked doors") but safe; they are
  marked `generated` in `data/entries.json`.
- A judge model is a noisy reviewer: it rejects good candidates and misses subtle ones, which is why it only
  vetoes sentences and the rules do the ranking.
- Word-vector neighbours describe a word in general, not one meaning, so they are only used for words with a
  single meaning.
- Words that Wiktionary and WordNet do not know get no card.

## Sources and licences

| Source | Used for | Licence |
|---|---|---|
| [English Wiktionary](https://en.wiktionary.org/), via [kaikki.org](https://kaikki.org/) | meanings, definitions, synonyms, examples | CC BY-SA 4.0 |
| [Simple English Wiktionary](https://simple.wiktionary.org/) | definitions, examples | CC BY-SA 4.0 |
| [Open English WordNet 2024](https://en-word.net/) | definitions, synonyms, broader terms, examples | CC BY 4.0 |
| [Tatoeba](https://tatoeba.org/) | example sentences | CC BY 2.0 FR |
| [GloVe wiki-gigaword-100](https://nlp.stanford.edu/projects/glove/) | related words | PDDL |
| [wordfreq](https://github.com/rspeer/wordfreq) | word frequency | CC BY-SA 4.0 |
| [bge-base-en-v1.5](https://huggingface.co/BAAI/bge-base-en-v1.5), [bge-reranker-large](https://huggingface.co/BAAI/bge-reranker-large), [nli-deberta-v3-base](https://huggingface.co/cross-encoder/nli-deberta-v3-base), [bart-large-mnli](https://huggingface.co/facebook/bart-large-mnli) | matching meanings and sentences, filtering | MIT, Apache 2.0 |
| [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) | speech | Apache 2.0 |

A deck contains text from Wiktionary and Tatoeba, so share it only with attribution to them and under
compatible terms.
