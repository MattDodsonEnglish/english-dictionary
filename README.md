# words.db

Dictionary entries for 167585 words in a parquet file, including IPA pronunciations, homoynm and meanings.
Built by sweeping every word of [dictionaryapi.dev](https://dictionaryapi.dev/).

As far as I know, this is the largest locally downloadable dictionary of English words in the world.

## Use

1. Download Parquet file.
2. Query using your favorite tool.

## Get the files

The [Releases](https://github.com/MattDodsonEnglish/english-dictionary/releases) has the `words.parquet`. This holds all the words that did not return a `404`.

If you have some special interest in the data, feel free to request the `raw_response.parquet`.

<details>
For historical interest, `raw_resposes.parquet` records the responses of all requests to the API, including the endpoints that returned a `404` status.
This is interesting only if you want to compare the working word corpus with the full `words.txt` list.
The `run-log.parquet` has metadata for each run. This is interesting only if you need a precise date for when range of entries was written to the database or if for some reason are interested in the job duration.
</details>

## Structure

The current schema has two columns:

- `word`. The head word. For example, "lead".
- `entries`. An array of complex JSON responses, one for each primary meaning of a word. Some words, like "lead", have multiple entries.

The structure of the entry is derived from the wikitionary page.
I'd like to rework the entry schema to make the dictionary more queryable, but for now you must deal with a complex JSON array.

Hello is a simple example:

<details>
<title>Hello</title>

```json
[
  {
    "word": "hello",
    "phonetic": "həˈləʊ",
    "phonetics": [
      {
        "text": "həˈləʊ",
        "audio": "//ssl.gstatic.com/dictionary/static/sounds/20200429/hello--_gb_1.mp3"
      },
      {
        "text": "hɛˈləʊ"
      }
    ],
    "origin": "early 19th century: variant of earlier hollo ; related to holla.",
    "meanings": [
      {
        "partOfSpeech": "exclamation",
        "definitions": [
          {
            "definition": "used as a greeting or to begin a phone conversation.",
            "example": "hello there, Katie!",
            "synonyms": [],
            "antonyms": []
          }
        ]
      },
      {
        "partOfSpeech": "noun",
        "definitions": [
          {
            "definition": "an utterance of ‘hello’; a greeting.",
            "example": "she was getting polite nods and hellos from people",
            "synonyms": [],
            "antonyms": []
          }
        ]
      },
      {
        "partOfSpeech": "verb",
        "definitions": [
          {
            "definition": "say or shout ‘hello’.",
            "example": "I pressed the phone button and helloed",
            "synonyms": [],
            "antonyms": []
          }
        ]
      }
    ]
  }
]
```

</details>

The structure of some entries is complex, especially if the same word has multiple meanings, pronunciations, etymologies and so on.

If curious, this query gives longest entries.

``` sql
select word,len(entries) len from 'entries.parquet'
order by len ASC;
```



## Query

Query the dictionary using any tool that can read parquet files.
I like [DuckDB](https://duckdb.org/docs/stable/data/parquet/overview.html).

For example, select a single word:

```sql
select entries from 'entries.parquet'
    WHERE word = 'fluff';
```

Select all words that contain the string `fluff`

```sql
select word from 'entries.parquet'
  WHERE word ILIKE '%fluff%';
```

Select all phonetic information about a set of words:

``` sql
select entries[0].phonetics from 'entries.parquet'
  WHERE word ILIKE '%fluff%';
```

Or do aggregations, counting all words that have a certain phonetic pattern.

```sql
select count(word) from 'entries.parquet'
  WHERE entries[0].phonetic ILIKE '%ʌmbɹ%';
```

("Penumbra" is an example of one of the 11 words in this set.)


Of course, you can find much deeper patterns with more complex query logic and functions.

## About

I made this because I was surprised to find it didn't exist.

### Why

The [Free Dictionary API](https://github.com/meetDeveloper/freeDictionaryAPI) made a great, free and open-source API for English words. But as far as I can tell, there is no way to self-host, and at the time of writing, the developer has been inactive for a few years.
Furthermore, there's no good way to aggregate and compare groups of words.

Since 2024, Wiktionary itself has an [API endpoint for definitions](https://en.wiktionary.org/api/rest_v1/#/Page%20content/get_page_definition__term_) but the response has much less information.

You can find many dictionary CSVs on Github and other sites, but usually these are old, taken from public-domain dictionaries, poorly standardized, and lacking information like IPA transcription.

Putting all the files in a local database solves all these problems. You have the full information in a single file, which you can use to build your own applications or do your own analysis.

### How this was built

The Free Dictionary API repository has a word list in a TXT file.

I used this word list as the input for a python script that:
1. Requested the word at `https://api.dictionaryapi.dev/api/v2/entries/en/<WORD>`
1. Wrote the word, entry, and metadata to DuckDb database.

At the beginning I wrote my own script and filtered the incoming response.
After an hour or two of starting and quickly discovering some missing information,
I realized an ELT pattern is better:
just write the entire response and then transform it later (transform is still #TODO). At this point I outsourced all work to Claude.

The file is in `db-builder/api-sweep.py`.

The script ran for five days (not continuously) with a few performance tweaks on the way.
In total, it took `101.23` hours to complete.

### Source of entries

The Dictionary API gets its definitions from Wikitionary.
The script ran intermittently from 2025-06-10 to 2025-06-15.
I don't know if the entries are from this pages on this date, or if the API uses some intermediate storage.


## TODOs and IDEAs {#todos}

- [ ] Document structure and mapping from source
- [ ] Make easier, more queryable schema
- [ ] Figure out convenient way to query by IPA phonemes
- [ ] Build dictionary app using WASM


## License

The code is AGPL.
All dictionary entries have a CC BY-SA 3.0 license, coming from Wikitionary as their source.

## Thanks

This project would be impossible without @meetdeveloper and the authors of wikitionary.
The FreeDictionary API did all the hard work here, I just ran a script.
