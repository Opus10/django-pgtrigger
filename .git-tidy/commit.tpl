# Remember - commit messages are used to generate release notes!
# Use the following template when writing a commit message or
# use "git tidy-commit" to commit a properly-formatted message.
#
# ---- Commit Message Format ----
#
# {{ schema.summary.help }}
#
# {{ schema.description.help }}
#
{% for entry in schema %}
{% if entry.label not in ['summary', 'description'] %}
# {{ entry.label.replace('_', '-').title() }}: {{ entry.help }}
{% endif %}
{% endfor %}