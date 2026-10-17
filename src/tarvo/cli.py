"""Run the deterministic financial baseline: python -m tarvo.cli."""
import argparse
import json

from tarvo.finance import run_close


def main():
    parser = argparse.ArgumentParser(description='Preparar fechamento Tarvo com rastro; não aprova nem emite notas.')
    parser.add_argument('--input-dir',default='contexto/data_pack')
    parser.add_argument('--output-dir',default='saida')
    parser.add_argument('--period',default='2026-09')
    args = parser.parse_args()
    print(json.dumps(run_close(args.input_dir,args.output_dir,args.period),ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
