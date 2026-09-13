import os
import glob
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

class RAGService:
    _vectorizer = None
    _tfidf_matrix = None
    _documents = []
    
    @classmethod
    def build_index(cls, kb_dir="knowledge_base"):
        """
        Reads text files from the knowledge base directory, chunks them,
        and builds a TF-IDF index for fast cosine similarity search.
        """
        # Get absolute path relative to project root
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        kb_path = os.path.join(base_dir, kb_dir)
        
        if not os.path.exists(kb_path):
            print(f"RAG Service: Knowledge base directory '{kb_path}' not found.")
            return
            
        files = glob.glob(os.path.join(kb_path, "*.txt"))
        cls._documents = []
        
        for file_path in files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Simple chunking: split by paragraphs
                    chunks = [chunk.strip() for chunk in content.split('\n\n') if len(chunk.strip()) > 20]
                    cls._documents.extend(chunks)
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
                
        if not cls._documents:
            print("RAG Service: No documents found in knowledge base.")
            return
            
        cls._vectorizer = TfidfVectorizer(stop_words='english')
        cls._tfidf_matrix = cls._vectorizer.fit_transform(cls._documents)
        print(f"RAG Service: Built index with {len(cls._documents)} document chunks.")

    @classmethod
    def search(cls, query, top_k=2):
        """
        Searches the RAG index for chunks similar to the query.
        Returns a single string containing the concatenated top chunks.
        """
        if cls._vectorizer is None or cls._tfidf_matrix is None or not cls._documents:
            return ""
            
        try:
            query_vec = cls._vectorizer.transform([query])
            similarities = cosine_similarity(query_vec, cls._tfidf_matrix).flatten()
            
            # Sort indices by similarity score descending
            top_indices = np.argsort(similarities)[::-1][:top_k]
            
            results = []
            for idx in top_indices:
                if similarities[idx] > 0.05:  # Lower threshold to ensure some context is returned for testing
                    results.append(cls._documents[idx])
                    
            if results:
                return "\n\n".join(results)
        except Exception as e:
            print(f"RAG Search error: {e}")
            
        return ""
