# Objective

This is a web application that displays data about electricity grids for countries around the world. For the end user, it is a static web site that they can browse to explore data about the energy transition for particular countries. On the backend, the app scrapes data from a variety of sources and places them in a local sqlite database. A key principle is that everything in this local database can be recomputed from external primary sources, so we don't need to worry about data resiliency.

A secondary objective is enabling the author to learn more about Python and Django. Please stick to normative standard project structure and approaches, and let me know if I am straying from established patterns.

# Tech stack

- Python 3.14
- Django 6.0.2.
- SQLite
- Ruff for python formatting. Please run ruff check and ruff format before committing.