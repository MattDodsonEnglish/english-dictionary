import requests
import json
import time
import duckdb
from datetime import datetime

INPUT_FILE = 'words.txt'
DB_FILE = 'words.duckdb'
API_URL = 'https://api.dictionaryapi.dev/api/v2/entries/en/{}'
REQUEST_DELAY = 1  # seconds
RATE_LIMIT_SLEEP = 300  # 5 minutes

def fetch_word_data(word, session):
    while True:
        start_time = time.perf_counter()
        try:
            response = session.get(API_URL.format(word))
            if response.status_code == 429:
                print("429 hit, sleeping for 5 minutes...")
                time.sleep(RATE_LIMIT_SLEEP)
                continue  # retry same word after sleeping
            
            # Try to parse as JSON first
            try:
                json_data = response.json()
                response_data = response.text  # Store original JSON text
            except json.JSONDecodeError:
                # If not JSON, wrap in a JSON object for storage
                json_data = None
                response_data = json.dumps({"error": "non_json_response", "content": response.text})
                print(f"Non-JSON response for '{word}', wrapping in JSON object")
            
            status_code = response.status_code
            request_duration = time.perf_counter() - start_time
            
            if response.status_code != 200:
                print(f"API error for '{word}': HTTP {status_code}")
                return None, response_data, status_code, request_duration
            
            print(f"Successfully fetched data for '{word}'")
            return json_data, response_data, status_code, request_duration
        except requests.RequestException as e:
            request_duration = time.perf_counter() - start_time
            print(f"Error fetching '{word}': {e}")
            # Wrap error message in JSON for storage
            error_json = json.dumps({"error": "request_exception", "message": str(e)})
            return None, error_json, 0, request_duration

def init_database():
    conn = duckdb.connect(DB_FILE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS word_responses (
            word VARCHAR PRIMARY KEY,
            responses JSON NOT NULL,
            status_code INTEGER NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS run_log (
            start_time TIMESTAMP PRIMARY KEY,
            end_time TIMESTAMP,
            start_word VARCHAR,
            end_word VARCHAR,
            words_processed INTEGER DEFAULT 0
        )
    """)
    return conn

def get_processed_words(conn):
    result = conn.execute("SELECT word FROM word_responses").fetchall()
    return set(row[0] for row in result)

def get_last_processed_word(conn):
    result = conn.execute("SELECT word FROM word_responses ORDER BY timestamp DESC LIMIT 1").fetchone()
    return result[0] if result else None

def find_word_position(word_list, target_word):
    if target_word is None:
        return 0
    try:
        return word_list.index(target_word) + 1
    except ValueError:
        print(f"Last processed word '{target_word}' not found in word list. Starting from beginning.")
        return 0

def store_word_response(conn, word, response_text, status_code):
    conn.execute(
        "INSERT OR REPLACE INTO word_responses (word, responses, status_code) VALUES (?, ?, ?)",
        [word, response_text, status_code]
    )
    conn.commit()

def start_run_log(conn, start_word):
    start_time = datetime.now()
    conn.execute(
        "INSERT INTO run_log (start_time, start_word) VALUES (?, ?)",
        [start_time, start_word]
    )
    conn.commit()
    return start_time

def end_run_log(conn, start_time, end_word, words_processed):
    conn.execute(
        "UPDATE run_log SET end_time=?, end_word=?, words_processed=? WHERE start_time=?",
        [datetime.now(), end_word, words_processed, start_time]
    )
    conn.commit()

def cleanup_incomplete_run_logs(conn):
    incomplete_runs = conn.execute(
        "SELECT start_time, start_word FROM run_log WHERE end_time IS NULL ORDER BY start_time"
    ).fetchall()
    
    for start_time, start_word in incomplete_runs:
        next_run = conn.execute(
            "SELECT start_time FROM run_log WHERE start_time > ? ORDER BY start_time LIMIT 1",
            [start_time]
        ).fetchone()
        
        if next_run:
            end_cutoff = next_run[0]
            word_data = conn.execute(
                "SELECT word, timestamp FROM word_responses WHERE timestamp >= ? AND timestamp < ? ORDER BY timestamp DESC LIMIT 1",
                [start_time, end_cutoff]
            ).fetchone()
            word_count = conn.execute(
                "SELECT COUNT(*) FROM word_responses WHERE timestamp >= ? AND timestamp < ?",
                [start_time, end_cutoff]
            ).fetchone()[0]
        else:
            word_data = conn.execute(
                "SELECT word, timestamp FROM word_responses WHERE timestamp >= ? ORDER BY timestamp DESC LIMIT 1",
                [start_time]
            ).fetchone()
            word_count = conn.execute(
                "SELECT COUNT(*) FROM word_responses WHERE timestamp >= ?",
                [start_time]
            ).fetchone()[0]
        
        if word_data:
            end_word, end_time = word_data
            conn.execute(
                "UPDATE run_log SET end_time=?, end_word=?, words_processed=? WHERE start_time=?",
                [end_time, end_word, word_count, start_time]
            )
            print(f"Fixed incomplete run log: {start_time} -> {end_time} ({word_count} words)")
        else:
            conn.execute(
                "UPDATE run_log SET end_time=?, end_word=?, words_processed=? WHERE start_time=?",
                [start_time, start_word, 0, start_time]
            )
            print(f"Fixed incomplete run log with no words processed: {start_time}")
    
    conn.commit()


def main():
    # Initialize database
    conn = init_database()
    
    # Clean up any incomplete run logs from previous crashes
    cleanup_incomplete_run_logs(conn)
    
    # Create HTTP session for connection reuse
    session = requests.Session()
    
    # Load all words from file
    with open(INPUT_FILE, 'r') as infile:
        all_words = [line.strip() for line in infile if line.strip()]
    
    # Get set of already processed words
    processed_words = get_processed_words(conn)
    
    # Find where to resume
    last_word = get_last_processed_word(conn)
    start_index = find_word_position(all_words, last_word)
    
    print(f"Total words in file: {len(all_words)}")
    if last_word:
        print(f"Resuming from word: '{last_word}' at position {start_index}")
    else:
        print("Starting from the beginning")
    
    # Start run logging
    start_word = all_words[start_index] if start_index < len(all_words) else "END"
    run_start_time = start_run_log(conn, start_word)
    
    words_processed = 0
    last_processed_word = start_word
    
    try:
        for i in range(start_index, len(all_words)):
            word = all_words[i]
            
            # Skip if already processed
            if word in processed_words:
                print(f"Skipping already processed word: '{word}' ({i+1}/{len(all_words)})")
                continue
                
            print(f"Processing word: '{word}' ({i+1}/{len(all_words)})")
            
            data, response_text, status_code, request_duration = fetch_word_data(word, session)
            
            # Store response in database
            store_word_response(conn, word, response_text, status_code)
            
            if data:
                print(f"Successfully stored data for '{word}'")
            else:
                print(f"Stored failed response for word '{word}'")
            
            words_processed += 1
            last_processed_word = word
            
            # Precise timing - sleep for remaining time to hit exactly 1 req/sec
            sleep_time = max(0, REQUEST_DELAY - request_duration)
            if sleep_time > 0:
                time.sleep(sleep_time)
    
    except KeyboardInterrupt:
        print("Interrupted by user")
    except Exception as e:
        print(f"Unexpected error: {e}")
    finally:
        # End run logging
        end_run_log(conn, run_start_time, last_processed_word, words_processed)
        session.close()
        conn.close()
        print(f"Run completed. Processed {words_processed} words. Last word: '{last_processed_word}'")

if __name__ == '__main__':
    main()
