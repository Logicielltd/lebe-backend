import logging
from datetime import datetime
from typing import Dict, Any
import pymongo
from pymongo import MongoClient
from loguru import logger
import json

class MongoDBHandler:
    def __init__(self, connection_string: str, database_name: str, collection_name: str):
        self.connection_string = connection_string
        self.database_name = database_name
        self.collection_name = collection_name
        self.client = None
        self.collection = None
        #self._connect()
    
    def _connect(self):
        try:
            self.client = MongoClient(self.connection_string)
            db = self.client[self.database_name]
            self.collection = db[self.collection_name]
            # Create index for better query performance
            self.collection.create_index([("timestamp", pymongo.DESCENDING)])
            self.collection.create_index([("level", pymongo.ASCENDING)])
            self.collection.create_index([("endpoint", pymongo.ASCENDING)])
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {str(e)}")
            raise
    
    def insert_log(self, log_data: Dict[str, Any]):
        try:
            if self.collection:
                self.collection.insert_one(log_data)
        except Exception as e:
            logger.error(f"Failed to insert log to MongoDB: {str(e)}")
    
    def close(self):
        if self.client:
            self.client.close()