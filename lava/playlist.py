import glob
import json
import uuid
from enum import Enum
from os import path
from typing import Optional, Union, List

class Mode(Enum):
    PRIVATE = 0
    GLOBAL = 1

class Playlist:
    def __init__(self, name: str, owner_id: int, public: bool, uid: str):
        self.name = name
        self.owner_id = owner_id
        self.public = public
        self.uid = uid

    @staticmethod
    def _generate_uid(name: str, user_id: int) -> str:
        return uuid.uuid5(uuid.NAMESPACE_DNS, str(user_id) + name).hex
    
    @classmethod
    def comparison(cls, playlist: "Playlist", user_id: int) -> Optional["Playlist"] | bool:  
        if playlist.public is False and playlist.owner_id != user_id:
            return False
        elif playlist.owner_id == user_id or playlist.public:
            return playlist
        else:
            return None
    
    @classmethod
    def find_playlist(cls, user_id: int, uid: str = None, mode: Mode = Mode.PRIVATE) -> Optional[Union[List["Playlist"], "Playlist", bool]]:
        if mode == Mode.PRIVATE:
            if uid is None:
                if user_id is not None:
                    
                    try:
                        with open(f"./playlist/{user_id}.json", "r", encoding="utf-8") as f:
                            data = json.load(f)

                        playlists = [
                            cls(name, user_id, data.get(name, {}).get('public', False), cls._generate_uid(name, user_id))
                            for name in data.keys()
                        ]
                        
                        return playlists[0] if len(playlists) == 1 else playlists
                    except FileNotFoundError:
                        return None
                else:
                    raise ValueError("No user ID provided.")
            else:
                return cls.from_uuid(uid, user_id)
        else:
            if uid is not None:
                playlist = cls.from_uuid(uid)
                comparison_result = cls.comparison(playlist, user_id)
                if comparison_result is False:
                    return False
                elif comparison_result is not None:
                    return comparison_result
                else:
                    return cls.get_item(playlist.uid)
            else:
                raise ValueError("No playlist ID provided.")

    
    @classmethod
    def get_item(cls, uid: str) -> Optional["Playlist"]:
        for file_path in glob.glob(path.join("playlist", "*.json")):
            filename = path.basename(file_path).split('.')[0]
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for name in data.keys():
                        if cls._generate_uid(name, int(filename)) == uid:
                            return cls(name, int(filename), data.get(name, {}).get('public', False), uid)
            except FileNotFoundError:
                continue
        return None
    
    @classmethod
    def from_uuid(cls, uid: str, user_id: int = None) -> "Playlist":
        item = cls.get_item(uid)
        if item is not None:
            return item
        raise ValueError(f"Playlist with UUID {uid} not found.")

    def to_dict(self) -> dict:
        item = self.get_item(self.uid)
        if item is not None:
            with open(f"./playlist/{self.owner_id}.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                return data
        raise ValueError(f"Playlist with UUID {self} not found.")

    def __repr__(self) -> str:
        return f"<Playlist name={self.name} owner_id={self.owner_id} public={self.public} uid={self.uid}>"