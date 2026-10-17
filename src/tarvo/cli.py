"""Run the deterministic financial baseline: python -m tarvo.cli."""
import argparse
import json

from tarvo.finance import run_close


def main():
    parser = argparse.ArgumentParser(description='Preparar fechamento Tarvo com rastro; não aprova nem emite notas.')
    parser.add_argument('--input-dir',default='contexto/data_pack')
    parser.add_argument('--output-dir',default='saida')
    parser.add_argument('--period',default='2026-09')
    parser.add_argument('--input-files-json',help='Trusted server-side JSON file: role to safe basename inside input-dir; optional')
    args = parser.parse_args()
    mapping=None
    if args.input_files_json:
        with open(args.input_files_json,encoding='utf-8') as fh:
            mapping=json.load(fh)
    print(json.dumps(run_close(args.input_dir,args.output_dir,args.period,input_files=mapping),ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
