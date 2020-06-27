{% if output == ':github/pr' %}
**Heads up!** This is what the release notes will look like based on the commits.

{% endif %}
{% if not range %}
# Changelog
{% endif %}
{% for tag, commits_by_tag in commits.exclude('summary', '.*\[skip ci\].*', match=True).group('tag').items() %}
## {{ tag|default('Unreleased', True) }} {% if tag.date %}({{ tag.date.date() }}){% endif %}

{% for type, commits_by_type in commits_by_tag.group('type', ascending_keys=True, none_key_last=True).items() %}
### {{ type|default('Other', True)|title }}
{% for commit in commits_by_type %}
{% if not commit.is_parsed %}
  - {{ commit.sha[:7] }}: Commit could not be parsed.
{% else %}
  - {{ commit.summary }} [{{ commit.author_name }}, {{ commit.sha[:7] }}]
{% if commit.description %}

    {{ commit.description|indent(4) }}
{% endif %}
{% endif %}
{% endfor %}
{% endfor %}

{% endfor %}