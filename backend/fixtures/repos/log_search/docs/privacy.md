# Privacy notes

- Logs are anonymised at ingest: user identifiers are replaced with a salted hash and IP
  addresses are dropped before the record reaches Elasticsearch.
- The assistant never sees raw user input from production systems, only log messages.
- No personal data is sent to the model provider. Prompts contain the engineer's question
  and up to 20 anonymised log lines.
- Log retention is 30 days, enforced by an index lifecycle policy.
