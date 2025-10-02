from pymongo import MongoClient
from config import settings

def create_indexes():
    client = MongoClient(settings.MONGO_URI)
    db = client[settings.MONGO_DB_NAME]
    collection = db["api_logs"]
    
    # Create indexes
    collection.create_index("timestamp")
    collection.create_index("level")
    collection.create_index("endpoint")
    collection.create_index("user_email")
    collection.create_index("status_code")
    
    print("MongoDB indexes created successfully")

if __name__ == "__main__":
    create_indexes()