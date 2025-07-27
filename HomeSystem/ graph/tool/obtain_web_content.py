from langchain_core.tools import BaseTool
from langchain_core.tools.base import ArgsSchema
from pydantic import BaseModel, Field
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import WebBaseLoader
from langchain_community.vectorstores import FAISS
from langchain_ollama.embeddings import OllamaEmbeddings
import hashlib
import bs4
from langchain.tools.retriever import create_retriever_tool


class ObtainWebContentToolInput(BaseModel):
    url: str = Field(description="The URL of the webpage to scrape")
    query: str = Field(description="The query to search the webpage")


class ObtainWebContentTool(BaseTool):
    name: str = "Scrape_web_content"
    description: str = "Scrape the text content from a specified webpage; use this tool for anything related to that webpage!"
    args_schema: ArgsSchema = ObtainWebContentToolInput
    return_direct: bool = False
    
    
    def __init__(self,
                 ollama_url: str = "http://localhost:11434",
                 ollama_model: str = "bge-m3",
                 chunk_size: int = 1000,
                 chunk_overlap: int = 200
                 ):
        super().__init__()
        
        self._retrievers = {}
        
        self._text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        
        self._embeddings = OllamaEmbeddings(
            base_url=ollama_url,
            model=ollama_model
        )
        

    def _run(self, url: str, query: str) -> str:
        """Use this tool to scrape the text content from a specified webpage"""
        
        # 使用MD5哈希函数生成URL的固定长度表示
        url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
        
        if url_hash not in self._retrievers:
            # 如果还没有对应的retriever，则创建一个新的
            self._retrievers[url_hash] = self.load_web_content(url)
            
        retriever_tool = self._retrievers[url_hash]
        
        # 使用retriever工具进行检索
        result = retriever_tool.invoke(query)
        
        return result
    
    def encode_url(self, url: str) -> str:
        """对url进行编码，降低url的长度，方便作为key存储"""
        # 使用MD5哈希函数生成URL的固定长度表示
        return hashlib.md5(url.encode('utf-8')).hexdigest()
    
    def load_web_content(self, url: str) -> str:
        """加载网页内容"""
        try:
            # First approach: Load the full page
            loader = WebBaseLoader(web_path=url)
            docs = loader.load()
            
            # Apply post-processing to filter out navigation and noise
            if docs and docs[0].page_content:
                # Clean the content by filtering out common navigation patterns
                content = docs[0].page_content
                
                # Split content into lines and apply filtering
                lines = content.split('\n')
                filtered_lines = []
                
                # Track current section to identify navigation blocks
                current_section = []
                navigation_patterns = ['home', 'menu', 'navigation', 'login', 'sign in', 'sign up', 
                                      'search', 'about us', 'contact', 'cookie', 'privacy', 'terms',
                                      'copyright', '©', 'all rights reserved', 'navigation', 'sitemap',
                                      'skip to content', 'share', 'follow us']
                
                # Process each line
                for line in lines:
                    line = line.strip()
                    
                    # Skip empty lines and very short lines (often menus)
                    if not line or len(line) < 3:
                        continue
                    
                    # Check if line contains navigation-related patterns
                    is_navigation = False
                    lower_line = line.lower()
                    
                    if len(line) < 20:  # Short lines are suspect for menus
                        for pattern in navigation_patterns:
                            if pattern in lower_line:
                                is_navigation = True
                                break
                    
                    # Skip this line if it looks like navigation
                    if is_navigation:
                        continue
                        
                    # Add line to filtered content
                    filtered_lines.append(line)
                
                # Rejoin the filtered content
                filtered_content = '\n'.join(filtered_lines)
                
                # Create a new document with filtered content
                from langchain_core.documents import Document
                filtered_doc = Document(
                    page_content=filtered_content,
                    metadata=docs[0].metadata
                )
                docs = [filtered_doc]
            
            # 文本分割
            docs = self._text_splitter.split_documents(docs)
            
            # 使用Ollama进行编码
            embeddings = self._embeddings
            vectordb = FAISS.from_documents(
                docs,
                embeddings,
            )
            
            # 保存向量数据库
            retriever = vectordb.as_retriever(
                search_kwargs={"k": 5}  # Return top 5 most relevant chunks
            )
            
            retriever_tool = create_retriever_tool( 
                retriever,
                "web_content_retriever",
                "Retrieve information from the web content"
            )
            
            return retriever_tool
            
        except Exception as e:
            logger.warning(f"Content filtering failed for {url}, using raw content: {e}")
            try:
                loader = WebBaseLoader(web_path=url)
                docs = loader.load()
                docs = self._text_splitter.split_documents(docs)
                vectordb = FAISS.from_documents(docs, self._embeddings)
                retriever = vectordb.as_retriever()
                
                return create_retriever_tool(
                    retriever,
                    "web_content_retriever",
                    "Retrieve information from the web content"
                )
            except Exception as fallback_error:
                logger.error(f"Fallback loading also failed for {url}: {fallback_error}")
                raise RuntimeError(f"Failed to load content from {url}: {fallback_error}")
    
    def _filter_navigation_content(self, content: str) -> str:
        """Filter out navigation and noise from web content.
        
        Args:
            content: Raw web content
            
        Returns:
            Filtered content with navigation removed
        """
        lines = content.split('\n')
        filtered_lines = []
        
        navigation_patterns = [
            'home', 'menu', 'navigation', 'login', 'sign in', 'sign up',
            'search', 'about us', 'contact', 'cookie', 'privacy', 'terms',
            'copyright', '©', 'all rights reserved', 'sitemap',
            'skip to content', 'share', 'follow us'
        ]
        
        for line in lines:
            line = line.strip()
            
            if not line or len(line) < 3:
                continue
            
            is_navigation = False
            if len(line) < 20:
                lower_line = line.lower()
                for pattern in navigation_patterns:
                    if pattern in lower_line:
                        is_navigation = True
                        break
            
            if not is_navigation:
                filtered_lines.append(line)
        
        return '\n'.join(filtered_lines)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    tool = ObtainWebContentTool()
    
    result = tool.invoke(input={
        "url": "https://docs.smith.langchain.com/overview",
        "query": "如何安装"
    })
    print(f"Result type: {type(result)}")
    print(f"Result: {result}")
