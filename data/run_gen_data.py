import json
import pickle
import argparse
import re
import collections
import string


def normalize_answer(s):
    """Lower text and remove punctuation, articles and extra whitespace."""

    def remove_articles(text):
        regex = re.compile(r'\b(a|an|the)\b', re.UNICODE)
        return re.sub(regex, ' ', text)

    def white_space_fix(text):
        return ' '.join(text.split())

    def remove_punc(text):
        exclude = set(string.punctuation)
        return ''.join(ch for ch in text if ch not in exclude)

    def lower(text):
        return text.lower()

    return white_space_fix(remove_articles(remove_punc(lower(s))))


def get_tokens(s):
    if not s: return []
    return normalize_answer(s).split()


def compute_f1(a_gold, a_pred):
    gold_toks = get_tokens(a_gold)
    pred_toks = get_tokens(a_pred)
    common = collections.Counter(gold_toks) & collections.Counter(pred_toks)
    num_same = sum(common.values())
    if len(gold_toks) == 0 or len(pred_toks) == 0:
        # If either is no-answer, then F1 is 1 if they agree, 0 otherwise
        return int(gold_toks == pred_toks)
    if num_same == 0:
        return 0
    precision = 1.0 * num_same / len(pred_toks)
    recall = 1.0 * num_same / len(gold_toks)
    f1 = (2 * precision * recall) / (precision + recall)
    return f1


def gen_pv_data(std_dev_file, preds_file, output_file):
    """
    generate data for plausible answer verifier
    Args:
        std_dev_file: official dev file
        preds_file: atrlp model prediction file
        output_file:

    Returns: a file

    """
    dev = json.load(open(std_dev_file, 'r', encoding='utf-8'))
    preds = json.load(open(preds_file, 'r', encoding='utf-8'))

    for article in dev['data']:
        for paragraph in article["paragraphs"]:
            for qa in paragraph['qas']:
                qid = qa['id']
                pred = preds[qid]
                qa['is_impossible'] = True
                qa['plausible_answers'] = [{'text': pred, 'answer_start': 1}]

    json.dump(dev, open(output_file, 'w', encoding='utf-8'))
    print("generate pv data finished! ")


def gen_answer_refine_file(std_dev_file, nbest_file, output_file, split):
    """
    generate answer refine file, for choose refine answer
    Args:
        std_dev_file: official dev file
        nbest_file: atrlp prediction nbest file

    Returns: a file

    """
    data = json.load(open(std_dev_file, 'r', encoding='utf-8'))
    all_nbest = pickle.load(open(nbest_file, 'rb'))
    count = 0

    for article in data['data']:
        for p in article['paragraphs']:
            # del p['context']
            new_qas = []
            for qa in p['qas']:
                qid = qa['id']
                gold_answers = qa['answers']
                if split != 'test' and not gold_answers:
                    continue
                nbest = all_nbest[qid][:5]

                most_text = nbest[0]['text']
                new_qa = []
                for i, nb in enumerate(nbest):
                    pred = nb['text']
                    if split == 'train':
                        a = qa['answers'][0]['text']
                        f1 = compute_f1(a, pred)
                    elif split == 'dev':
                        f1 = max(compute_f1(a['text'], pred) for a in gold_answers)
                    else:
                        f1 = 0.
                    if pred in most_text or most_text in pred:
                        new_qa.append({"f1_score": f1,
                                       "pred_answer": pred,
                                       "question": qa['question'],
                                       "id": f"{qid}_{i}"})
                if split == 'train':
                    if new_qa[0]["f1_score"] > 0:
                        new_qas.extend(new_qa)
                else:
                    new_qas.extend(new_qa)
            p['qas'] = new_qas
            count += len(new_qas)

    print(count)

    json.dump(data, open(output_file, 'w', encoding='utf-8'))
    print("generate answer refine file finished! ")


def main():
    parser = argparse.ArgumentParser()

    # Required parameters
    parser.add_argument('--run-type', required=True, help="Generate data type : pv or reg")
    parser.add_argument('--std-dev-file', required=True, help="Official eval file")
    parser.add_argument('--input-file', required=True, help="Previous model output ")
    parser.add_argument("--output-file", required=True, help="Generate data output")
    parser.add_argument("--split", required=False, help="data type")
    args = parser.parse_args()

    if args.run_type == 'pv':
        gen_pv_data(args.std_dev_file, args.input_file, args.output_file)
    elif args.run_type == 'reg':
        gen_answer_refine_file(args.std_dev_file, args.input_file, args.output_file, args.split)
    else:
        raise


if __name__ == '__main__':
    main()
