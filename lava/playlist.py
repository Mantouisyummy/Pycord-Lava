import glob
import json
import uuid

from os import path

class Playlist:
    def __init__(self, name: str = "", user_id: int = -1, public: bool = False) -> None:
        self.name = name
        self.user_id = user_id
        self.public = public
    
    def get_item(uid: str):
        for file_path in glob.glob(path.join("playlist", "*.json")):
            filename = path.basename(file_path).split('.')[0]

            with open(f"./playlist/{int(filename)}.json","r",encoding="utf-8") as f:
                data = json.load(f)

            for i in data.keys():
                if uuid.uuid5(uuid.NAMESPACE_DNS, str(filename) + i).hex == uid:
                    user_id: int = int(filename)
                    title: str = i
                    public: bool = data[i]['public']
                    return title, user_id, public
        return None
                        

    def __repr__(self) -> str:
        return "<Playlist name={0.name} uuid={0.user_id} public={0.public}>".format(self)

    @classmethod
    def from_uuid(cls, uid: str):
        title, user_id, public = cls.get_item(uid)
        return cls(title, user_id, public)