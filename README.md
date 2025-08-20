# words.parquet

Dictionary entries for 167585 words in a parquet file, including IPA pronunciations, homoynm and meanings.
Built by sweeping every word of [dictionaryapi.dev](https://dictionaryapi.dev/).

As far as I know, this is the largest locally downloadable dictionary of English words in the world.


## Use

1. Download Parquet file.
2. Query using your favorite tool.

### Get the files

The [Releases](https://github.com/MattDodsonEnglish/english-dictionary/releases) has the `words.parquet`. This holds all the words from [`words.txt`](db-builder/words.txt) that did not return a `404`.

If you have some special interest in the data, feel free to request the `raw_response.parquet`, which includes metadata about run dates and duration.

### Structure

The current schema has two columns:

- `word`. The head word. For example, "lead".
- `entries`. An array of complex JSON responses, one for each primary meaning of a word. Some words, like "lead", have multiple entries.

The structure of the entry is derived from the wikitionary page.
I'd like to rework the entry schema to make the dictionary more queryable, but for now you must deal with a complex JSON array.

Hello is a simple example:

<details>
  <summary><h3>JSON payload for hello</h3></summary>
  
```json
[
  {
    "word": "hello",
    "phonetics": [
      {
        "audio": "https://api.dictionaryapi.dev/media/pronunciations/en/hello-au.mp3",
        "sourceUrl": "https://commons.wikimedia.org/w/index.php?curid=75797336",
        "license": {
          "name": "BY-SA 4.0",
          "url": "https://creativecommons.org/licenses/by-sa/4.0"
        }
      },
      {
        "text": "/həˈləʊ/",
        "audio": "https://api.dictionaryapi.dev/media/pronunciations/en/hello-uk.mp3",
        "sourceUrl": "https://commons.wikimedia.org/w/index.php?curid=9021983",
        "license": {
          "name": "BY 3.0 US",
          "url": "https://creativecommons.org/licenses/by/3.0/us"
        }
      },
      {
        "text": "/həˈloʊ/",
        "audio": ""
      }
    ],
    "meanings": [
      {
        "partOfSpeech": "noun",
        "definitions": [
          {
            "definition": "\"Hello!\" or an equivalent greeting.",
            "synonyms": [],
            "antonyms": []
          }
        ],
        "synonyms": [
          "greeting"
        ],
        "antonyms": []
      },
      {
        "partOfSpeech": "verb",
        "definitions": [
          {
            "definition": "To greet with \"hello\".",
            "synonyms": [],
            "antonyms": []
          }
        ],
        "synonyms": [],
        "antonyms": []
      },
      {
        "partOfSpeech": "interjection",
        "definitions": [
          {
            "definition": "A greeting (salutation) said when meeting someone or acknowledging someone’s arrival or presence.",
            "synonyms": [],
            "antonyms": [],
            "example": "Hello, everyone."
          },
          {
            "definition": "A greeting used when answering the telephone.",
            "synonyms": [],
            "antonyms": [],
            "example": "Hello? How may I help you?"
          },
          {
            "definition": "A call for response if it is not clear if anyone is present or listening, or if a telephone conversation may have been disconnected.",
            "synonyms": [],
            "antonyms": [],
            "example": "Hello? Is anyone there?"
          },
          {
            "definition": "Used sarcastically to imply that the person addressed or referred to has done something the speaker or writer considers to be foolish.",
            "synonyms": [],
            "antonyms": [],
            "example": "You just tried to start your car with your cell phone. Hello?"
          },
          {
            "definition": "An expression of puzzlement or discovery.",
            "synonyms": [],
            "antonyms": [],
            "example": "Hello! What’s going on here?"
          }
        ],
        "synonyms": [],
        "antonyms": [
          "bye",
          "goodbye"
        ]
      }
    ],
    "license": {
      "name": "CC BY-SA 3.0",
      "url": "https://creativecommons.org/licenses/by-sa/3.0"
    },
    "sourceUrls": [
      "https://en.wiktionary.org/wiki/hello"
    ]
  }
]
```

</details>

Many entries are more complex, with many nested arrays. Generally the more meanings and pronunciations a word has, the more complex its entry.

If curious, this query gives the longest entries by JSON length.

``` sql
select word,len(entries) len from 'entries.parquet'
order by len ASC;
```

### Query

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

Or do aggregations, counting all words that have a certain phonetic pattern. ("Penumbra" is an example of one of the 11 words in this set.)


```sql
select count(word) from 'entries.parquet'
  WHERE entries[0].phonetic ILIKE '%ʌmbɹ%';
```

Of course, you can find much deeper patterns with more complex query logic and functions.

## About

I made this because I was surprised to find it didn't exist.

### Why

The [Free Dictionary API](https://github.com/meetDeveloper/freeDictionaryAPI) is a great, free and open-source API for English words. But as far as I can tell, there is no way to self-host, and at the time of writing, the developer has been inactive for a few years.
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
I don't know if the entries are from the pages on this date, or if the API uses some intermediate storage.


## TODOs

- [ ] Document structure and mapping from source
- [ ] Make easier, more queryable schema
- [ ] Figure out convenient way to query by IPA phonemes
- [ ] Build dictionary app using WASM
- [ ] Host in object storage


## License

The code is AGPL.
All dictionary entries have a CC BY-SA 3.0 license, coming from Wikitionary as their source.

## Thanks

This project would be impossible the authors of Wiktionary and, more importantly, the work of @meetdeveloper.
The FreeDictionary API did all the hard work here, I just ran a script and wrote a README.
