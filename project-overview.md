# Objective

This is a web application that displays data about electricity grids for countries around the world. For the end user, it is a static web site that they can browse to explore data about the energy transition for particular countries. On the backend, the app scrapes data from a variety of sources and places them in a local sqlite database. A key principle is that everything in this local database can be recomputed from external primary sources, so we don't need to worry about data resiliency.

A secondary objective is enabling the author to learn more about Python and Django. Please stick to normative standard project structure and approaches, and let me know if I am straying from established patterns.

# Tech stack

- Python 3.14
- uv for environment management. Always use uv to run python.
- Django 6.0.2.
- SQLite (local) / Postgres (production)
- Ruff for python formatting. Please run ruff check and ruff format on all changes.

# Data sources

This project uses source data from several different organizations. Since each organization has slightly varying methodologies, it is important that we never directly compare or combine data together from multiple sources. For electricity generation data, Ember is the preferred data source. For total energy supply and primary energy sources, we use data from the Energy Institute's data sets.

# General instructions

- Don't reformat or modify unrelated parts of the code when you make a change. The diff for each change should always be relevant to the change that I requested. I don't like to mix cosmetic and behavioural changes in the same commit.
- I am an experienced developer, you don't need to offer to make trivial code changes for me.
- Please ask clarifying questions if there are key technical decisions to make and you have low confidence in the right choice or believe it is subjective.
