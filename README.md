# Using Datastar with Python - FastAPI

This project demonstrates two approaches to implementing the `DataStar` functionality in Python using FastAPI.

## Datastar
http://data-star.dev
https://github.com/delaneyj/datastar

## Files
- **main_1.py**: Contains the `DataStar` functionality directly within the script, uses a simpler, more direct approach with separate classes for fragments and signals,
- **main_2.py**: Utilizes the `datastar.py` module to implement the `DataStar` functionality.
- **datastar/datastar.py:** Contains the `DataStar` functionality in a separate module.

## Dependencies
Make sure to install any required dependencies by running:
```sh
pip install -r requirements.txt
```

## Usage
Choose either main_1.py or main_2.py based on your preference for direct implementation or modular approach.
```sh
uvicorn main_1:app
uvicorn main_2:app
```
