"""
Paper Analysis Agent Usage Example

This example demonstrates how to use the redesigned PaperAnalysisAgent with parallel LLM extraction
to analyze English academic papers and extract structured information efficiently.

New Features:
- Parallel extraction using 3 specialized LLM tools
- Keywords synthesized from extracted content (saves tokens)
- 3x faster than iterative approach
- Better specialization for different field types
"""
import sys
import json
from pathlib import Path

# Add the project root to the path
sys.path.append(str(Path(__file__).parent.parent))

from HomeSystem.graph.paper_analysis_agent import PaperAnalysisAgent, PaperAnalysisConfig
from loguru import logger


def example_paper_text():
    """Sample paper text for demonstration"""
    return """
    Abstract
    This paper presents a novel approach to natural language processing using transformer-based models. 
    We introduce a new architecture that improves upon existing methods by incorporating attention mechanisms 
    with enhanced contextual understanding. Our experiments on multiple benchmark datasets show significant 
    improvements in accuracy and computational efficiency.

    1. Introduction
    Natural language processing (NLP) has seen remarkable advances in recent years, particularly with the 
    introduction of transformer architectures. However, existing models still face challenges in understanding 
    long-range dependencies and contextual relationships in complex texts. This work addresses these limitations 
    by proposing a novel transformer variant with improved attention mechanisms.

    2. Related Work
    Previous work in transformer architectures includes BERT, GPT, and T5 models. While these models have 
    achieved state-of-the-art results on many tasks, they suffer from computational inefficiency and limited 
    contextual understanding in certain scenarios.

    3. Methodology
    Our approach consists of three main components: (1) Enhanced attention mechanism with multi-scale features, 
    (2) Contextual embedding layer with dynamic weighting, and (3) Efficient training strategy using curriculum 
    learning. We implement these components using PyTorch and train on a distributed computing cluster.

    4. Experiments
    We evaluate our model on three benchmark datasets: GLUE, SuperGLUE, and SQuAD. Our model achieves 
    92.3% accuracy on GLUE, 89.7% on SuperGLUE, and 94.1% F1 score on SQuAD, representing improvements 
    of 3.2%, 4.1%, and 2.8% respectively over previous state-of-the-art methods.

    5. Results and Discussion
    The experimental results demonstrate the effectiveness of our proposed approach. The enhanced attention 
    mechanism contributes most significantly to the performance gains, while the contextual embedding layer 
    provides better semantic understanding. The curriculum learning strategy reduces training time by 25%.

    6. Limitations
    Our approach has several limitations: (1) Increased model complexity compared to baseline transformers, 
    (2) Higher memory requirements during training, and (3) Limited evaluation on non-English languages.

    7. Conclusion
    We have presented a novel transformer architecture with enhanced attention mechanisms that achieves 
    state-of-the-art results on multiple NLP benchmarks. The proposed method addresses key limitations of 
    existing models while maintaining computational feasibility.

    8. Future Work
    Future research directions include: (1) Extending the model to multilingual settings, (2) Investigating 
    few-shot learning capabilities, and (3) Applying the approach to other domains such as computer vision.

    References
    [1] Vaswani, A., et al. Attention is all you need. NIPS 2017.
    [2] Devlin, J., et al. BERT: Pre-training of deep bidirectional transformers. NAACL 2019.
    [3] Brown, T., et al. Language models are few-shot learners. NeurIPS 2020.
    """


def basic_usage_example():
    """Basic usage example with default configuration"""
    logger.info("=== Basic Usage Example ===")
    
    # Create agent with default configuration
    agent = PaperAnalysisAgent()
    
    # Get sample paper text
    paper_text = example_paper_text()
    
    # Analyze the paper
    logger.info("Starting paper analysis...")
    result = agent.analyze_paper(paper_text)
    
    # Print results
    logger.info("Analysis completed!")
    print("\nAnalysis Result:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    # Extract structured result
    structured_result = agent.get_structured_result(result)
    if structured_result:
        logger.info("Successfully extracted structured result")
        print("\nStructured Result (8 fields):")
        print(json.dumps(structured_result, indent=2, ensure_ascii=False))
    else:
        logger.warning("Failed to extract structured result")


def custom_config_example():
    """Example with custom configuration for parallel extraction"""
    logger.info("=== Custom Configuration Example ===")
    
    # Create custom configuration
    config = PaperAnalysisConfig(
        model_name="ollama.Qwen3_30B",
        parallel_execution=True,  # Enable parallel processing
        validate_results=True,    # Enable result validation
        memory_enabled=False
    )
    
    # Create agent with custom config
    agent = PaperAnalysisAgent(config=config)
    
    # Get sample paper text
    paper_text = example_paper_text()
    
    # Analyze the paper
    logger.info("Starting paper analysis with custom config...")
    result = agent.analyze_paper(paper_text, thread_id="custom_analysis")
    
    # Print configuration info
    print(f"\nConfiguration used:")
    print(f"- Model: {config.model_name}")
    print(f"- Parallel execution: {config.parallel_execution}")
    print(f"- Validate results: {config.validate_results}")
    
    # Print results
    print("\nAnalysis Result:")
    print(json.dumps(result, indent=2, ensure_ascii=False))


def config_file_example():
    """Example using configuration file"""
    logger.info("=== Configuration File Example ===")
    
    # Path to configuration file
    config_path = Path(__file__).parent.parent / "HomeSystem" / "graph" / "config" / "paper_analysis_config.json"
    
    if config_path.exists():
        # Create agent from config file
        agent = PaperAnalysisAgent(config_path=str(config_path))
        
        # Get sample paper text
        paper_text = example_paper_text()
        
        # Analyze the paper
        logger.info("Starting paper analysis with config file...")
        result = agent.analyze_paper(paper_text, thread_id="file_config_analysis")
        
        # Print results
        print(f"\nUsing configuration file: {config_path}")
        print("\nAnalysis Result:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        # Show only the structured analysis part
        if "analysis" in result:
            print("\nExtracted Analysis:")
            print(json.dumps(result["analysis"], indent=2, ensure_ascii=False))
    else:
        logger.error(f"Configuration file not found: {config_path}")


def parallel_performance_example():
    """Example focusing on parallel execution performance"""
    logger.info("=== Parallel Performance Example ===")
    
    # Create agent with performance monitoring
    config = PaperAnalysisConfig(
        parallel_execution=True,
        validate_results=True,
        memory_enabled=False
    )
    
    agent = PaperAnalysisAgent(config=config)
    
    # Get sample paper text
    paper_text = example_paper_text()
    
    # Analyze the paper with timing
    import time
    logger.info("Starting paper analysis with parallel execution...")
    start_time = time.time()
    result = agent.analyze_paper(paper_text, thread_id="performance_analysis")
    end_time = time.time()
    
    # Show performance metrics
    execution_time = end_time - start_time
    print(f"\nPerformance Metrics:")
    print(f"- Execution time: {execution_time:.2f} seconds")
    print(f"- Extraction method: {result.get('extraction_method', 'unknown')}")
    print(f"- Completed tasks: {result.get('completed_tasks', 0)}/3")
    
    # Show extraction errors if any
    extraction_errors = result.get("extraction_errors", [])
    if extraction_errors:
        print(f"\nExtraction Errors ({len(extraction_errors)}):")
        for error in extraction_errors:
            print(f"- {error}")
    else:
        print("\nNo extraction errors - all parallel tasks completed successfully!")
    
    # Show field completeness
    if "analysis" in result:
        analysis = result["analysis"]
        field_counts = {}
        for field, content in analysis.items():
            if isinstance(content, list):
                field_counts[field] = len(content)
            elif isinstance(content, str):
                field_counts[field] = len(content)
            else:
                field_counts[field] = 0
        
        print(f"\nField Completeness:")
        for field, count in field_counts.items():
            status = "✓" if count > 0 else "✗"
            print(f"- {field}: {status} ({count} chars/items)")
    
    # Show the final structured result
    structured_result = agent.get_structured_result(result)
    if structured_result:
        print("\nFinal Structured Result:")
        print(json.dumps(structured_result, indent=2, ensure_ascii=False))


def main():
    """Run all examples"""
    logger.info("Starting Paper Analysis Agent Examples")
    
    try:
        # Run basic example
        basic_usage_example()
        print("\n" + "="*50 + "\n")
        
        # Run custom config example
        custom_config_example()
        print("\n" + "="*50 + "\n")
        
        # Run config file example
        config_file_example()
        print("\n" + "="*50 + "\n")
        
        # Run parallel performance example
        parallel_performance_example()
        
        logger.info("All examples completed successfully!")
        
    except Exception as e:
        logger.error(f"Example execution failed: {e}")
        raise


if __name__ == "__main__":
    main()