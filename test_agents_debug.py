#!/usr/bin/env python
"""
Test script para debuggear los agentes y parsers
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from agents.fundamental_agent import create_fundamental_agent
from agents.sentiment_agent import create_sentiment_agent
from agents.technical_agent import create_technical_agent
from crewai import Task, Crew, Process
from core.analysis_schemas import (
    parse_fundamental_analysis,
    parse_sentiment_analysis,
    parse_technical_analysis
)
from dataclasses import asdict

def test_agent(agent_name: str, ticker: str = "AAPL"):
    """Prueba un agente individual"""
    print(f"\n{'='*70}")
    print(f"TESTING {agent_name} with {ticker}")
    print(f"{'='*70}\n")

    if agent_name == "fundamental":
        agent = create_fundamental_agent()
        task = Task(
            description=f"Analiza los fundamentos de {ticker}",
            agent=agent,
            expected_output="JSON válido"
        )
        parser = parse_fundamental_analysis
    elif agent_name == "sentiment":
        agent = create_sentiment_agent()
        task = Task(
            description=f"Analiza sentimiento de {ticker}",
            agent=agent,
            expected_output="JSON válido"
        )
        parser = parse_sentiment_analysis
    else:  # technical
        agent = create_technical_agent()
        task = Task(
            description=f"Analiza técnico de {ticker}",
            agent=agent,
            expected_output="JSON válido"
        )
        parser = parse_technical_analysis

    try:
        print(f"[1] Creando crew...")
        crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)

        print(f"[2] Ejecutando kickoff...")
        result = crew.kickoff()

        print(f"[3] Tipo de resultado: {type(result).__name__}")
        print(f"[4] String conversion (primeros 500 chars):")
        output_str = str(result)
        print(output_str[:500])

        print(f"\n[5] Parseando con {agent_name}_parser...")
        parsed = parser(output_str)

        print(f"[6] Resultado parseado:")
        result_dict = asdict(parsed)
        import json
        print(json.dumps(result_dict, indent=2, ensure_ascii=False, default=str))

        print(f"\n✅ {agent_name} completado exitosamente")
        return True

    except Exception as e:
        print(f"\n❌ Error en {agent_name}: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    ticker = "AAPL"

    # Probar fundamental
    test_agent("fundamental", ticker)

    # Probar sentiment
    test_agent("sentiment", ticker)

    # Probar technical
    test_agent("technical", ticker)
