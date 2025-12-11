# backend/app/rag/vector_store.py

import os
import shutil
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data", "regulations")
DB_PATH = os.path.join(BASE_DIR, "data", "chromadb_storage")

def load_documents():
    docs = []
    
    if not os.path.exists(DATA_DIR):
        print(f"오류 : 데이터 폴더가 없습니다: {DATA_DIR}")
        return []

    for root, dirs, files in os.walk(DATA_DIR):
        for file in files:
            file_path = os.path.join(root, file)
            folder_name = os.path.basename(root)
            
            category = "general"
            if "internal_rules" in folder_name: category = "internal_rule"
            elif "public_products" in folder_name: category = "product"
            elif "guidelines" in folder_name: category = "guideline"

            try:
                loaded_docs = []
                if file.endswith(".pdf"):
                    print(f"[PDF 로드] {category}: {file}")
                    loader = PyPDFLoader(file_path)
                    loaded_docs = loader.load()
                elif file.endswith(".txt"):
                    print(f"[TXT 로드] {category}: {file}")
                    loader = TextLoader(file_path, encoding='utf-8')
                    loaded_docs = loader.load()
                
                for doc in loaded_docs:
                    doc.metadata["category"] = category
                    doc.metadata["source_file"] = file
                
                docs.extend(loaded_docs)
                
            except Exception as e:
                print(f"!!! 로드 실패 ({file}): {e}")

    return docs

def init_vector_db(reset=True):
    if reset and os.path.exists(DB_PATH):
        print("기존 벡터 DB 삭제")
        shutil.rmtree(DB_PATH)

    documents = load_documents()
    if not documents:
        print("오류 : 로드된 문서가 없습니다.")
        return

    #chunking
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", " ", ""]
    )
    splits = text_splitter.split_documents(documents)
    print(f"문서 분할 완료: 총 {len(splits)}개 청크 생성")

    #DB저장
    Chroma.from_documents(
        documents=splits,
        embedding=OpenAIEmbeddings(),
        persist_directory=DB_PATH
    )
    print(f"chromadb에 저장, 경로: {DB_PATH}")

def get_retriever():
    vector_db = Chroma(
        persist_directory=DB_PATH,
        embedding_function=OpenAIEmbeddings()
    )
    
    return vector_db.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 4}
    )

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    init_vector_db(reset=True)