from fastapi import HTTPException
from pydantic import BaseModel


class StorageBaser:
    def __init__(self, file: BaseModel):
        self.curr_file = file
        self.action = file.action

    def snapshotFile(self):
        """Checks if the file exists in the specified storage reference by attempting to open it."""
        try:
            file_path = f"{self.curr_file.storageref}/{self.curr_file.filename}"

            # Attempt to open the file
            with open(file_path, "rb") as file:
                file.read(
                    1
                )  # Read the first byte to ensure the file opens successfully

            return {"status": "success", "message": "File is available."}

        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="File not found.")
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error in whencomplete: {str(e)}"
            )

    def takeurl(self):
        """Combines the storage reference and filename into a full URL."""
        try:
            # Simulate creating the file URL
            url = f"{self.curr_file.storageref}/{self.curr_file.filename}"
            return {"status": "success", "url": url}

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error in takeurl: {str(e)}")

    def returns(self):
        """Call the appropriate method based on the action."""
        try:
            if self.action == "snapfile":
                result = self.snapshotFile()
            elif self.action == "takeurl":
                result = self.takeurl()
            else:
                raise HTTPException(status_code=400, detail="Invalid action")

            return result
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error processing request: {str(e)}"
            )
