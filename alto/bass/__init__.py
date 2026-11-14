"""Bass: Alto without Claude. The engine that builds and edits timelines for someone who has no
Claude subscription, using Anthropic's API on Alto's own account, metered in credits.

Nothing in this package talks to Anthropic unless client.make_client("live") has been switched on (see
client.py). Everything else runs against mock_anthropic, a faithful simulation behind the real SDK."""
