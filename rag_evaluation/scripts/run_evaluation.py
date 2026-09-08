"""
Simple RAGAS Evaluation Script
"""

import asyncio
from pathlib import Path
import json
import pandas as pd
from ragas.llms import llm_factory
from ragas.metrics.collections import Faithfulness, AnswerRelevancy, ContextPrecision, ContextRecall
from openai import AsyncOpenAI    # Instead of langchain_openai import ChatOpenAI
from ragas.embeddings import OpenAIEmbeddings    # Instead of from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

DATASET_PATH = BASE_DIR / "datasets" / "ragas_evaluation_dataset-1.json"
RESULTS_PATH = BASE_DIR / "datasets" / "results.csv"


# ---------------------------------------------------------
# Ragas setup
# ---------------------------------------------------------

client = AsyncOpenAI()

embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small",
    client=client
)

llm = llm_factory(
    "gpt-4o-mini",
    client=client,
)

faithfulness = Faithfulness(llm=llm)
answer_relevancy = AnswerRelevancy(llm=llm, embeddings=embeddings)
# context_precision = ContextPrecision(llm=llm)
# context_recall = ContextRecall(llm=llm)


# ---------------------------------------------------------
# Evaluation
# ---------------------------------------------------------

async def evaluate_dataset():

    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    results = []

    for index, item in enumerate(data, start=1):

        question = item["question"]
        answer = item["answer"]
        contexts = item["contexts"]

        print(f"[{index}/{len(data)}] Evaluating: {question}")

        # Faithfulness
        faithfulness_result = await faithfulness.ascore(
            user_input=question,
            response=answer,
            retrieved_contexts=contexts,
        )

        # Answer Relevancy
        answer_relevancy_result = await answer_relevancy.ascore(
            user_input=question,
            response=answer,
        )
        
        # context_precision_result = await context_precision.ascore(
        #     user_input=item["question"],
        #     reference=item["reference"],
        #     retrieved_contexts=item["contexts"],
        # )
        
        # context_recall_result = await context_recall.ascore(
        #     user_input=item["question"],
        #     reference=item["reference"],
        #     retrieved_contexts=item["contexts"],
        # )

        results.append({
            "question": question,
            "answer": answer,
            "faithfulness": faithfulness_result.value,
            "answer_relevancy": answer_relevancy_result.value,
        })

        print(
            f"    Faithfulness: {faithfulness_result.value:.4f}"
        )
        print(
            f"    Answer Relevancy: {answer_relevancy_result.value:.4f}"
        )
        
        
    # -----------------------------------------------------
    # Save results
    # -----------------------------------------------------

    df = pd.DataFrame(results)

    df.to_csv(RESULTS_PATH, index=False)

    print(f"\n✅ Detailed results saved to: {RESULTS_PATH}")


if __name__ == "__main__":
    asyncio.run(evaluate_dataset())
    