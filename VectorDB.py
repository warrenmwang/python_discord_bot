import chromadb
from chromadb.utils import embedding_functions
import uuid

class VectorDB:
    def __init__(self, data_path:str, embed_model:str, collection_name:str):
        self.data_path = data_path
        self.embed_model = embed_model
        self.collection_name = collection_name
        self.collection = self._getOrCreateChromaDB()

    def _getOrCreateChromaDB(self) -> chromadb.Collection:
        '''
        Create a new ChromaDB collection with the given data path, collection name, and embedding model
        '''
        client = chromadb.PersistentClient(path=self.data_path)
        embedding_func = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=self.embed_model)
        collection = client.get_or_create_collection(name=self.collection_name, embedding_function=embedding_func, metadata={"hnsw:space": "cosine"})
        return collection

    def upload(self, document:str, metadata:dict|None=None) -> None:
        '''
        Insert into the db the document (just a str) and any metadata (optional json/dict of values)
        '''
        self.collection.add(
            documents=[document],
            ids=[str(uuid.uuid4())],
            metadatas=[metadata] if metadata is not None else None
        )

    def query(self, prompt:str, k:int=1) -> list[str]:
        '''
        Query db and return the top k (default 1) responses
        responses are ordered by increasing distance 
        NOTE: optionally can use metadata and a constraint that says response must contain a particular string
        '''
        response = self.collection.query(
            query_texts=[prompt],
            n_results=k 
        )
        return response['documents'][0]

    def size(self) -> int:
        return self.collection.count()

if __name__ == '__main__':
    CHROMA_DATA_PATH = "chroma_data/"
    EMBED_MODEL = "all-MiniLM-L6-v2"
    COLLECTION_NAME = "test1"

    db = VectorDB(CHROMA_DATA_PATH, EMBED_MODEL, COLLECTION_NAME)

    print("Uploading documents...")
    db.upload('pizza is delicious and contains many calories although it can be unhealthy long term.')
    db.upload('apples and cranberries are the best fruits known to mankind.')
    db.upload('pineapple on pizza is absolutely divine -- pizza lover 49')
    print(f"db now has {db.size()} embeddings")

    print("Querying...")
    print(db.query("what are good fruits?",k=3))
