import csv
import io
import unittest
import zipfile
from types import SimpleNamespace
from bookmaker_lab import parse_historical_csv, expand_historical_files


def upload(name,raw):
    return SimpleNamespace(name=name,getvalue=lambda:raw)

def csv_upload(**changes):
    row=dict(Div='E0',Date='10/08/2025',HomeTeam='Home',AwayTeam='Away',FTHG='2',FTAG='1',B365CH='2',B365CD='3.5',B365CA='4',PSCH='1.9',PSCD='3.6',PSCA='4.1',AvgCH='2.1',AvgCD='3.4',AvgCA='3.9',B365H='2.2',B365D='3.2',B365A='3.8')
    row.update(changes)
    text=io.StringIO();writer=csv.DictWriter(text,fieldnames=list(row));writer.writeheader();writer.writerow(row)
    return upload('E0.csv',text.getvalue().encode())

class ClosingImportTests(unittest.TestCase):
    def test_default_uses_one_bookmaker_closing_trio(self):
        matches,rejected=parse_historical_csv([csv_upload()])
        self.assertEqual(rejected,0);self.assertEqual(matches[0]['_odds'],[2,3.5,4]);self.assertEqual(matches[0]['_provider'],'B365');self.assertEqual(matches[0]['_odds_type'],'closing')

    def test_missing_selected_book_does_not_fall_back_to_other_book(self):
        matches,_=parse_historical_csv([csv_upload(B365CH='',B365H='',B365D='',B365A='')])
        self.assertIsNone(matches[0]['_odds'])

    def test_opening_is_labelled_opening(self):
        matches,_=parse_historical_csv([csv_upload(B365CH='')])
        self.assertEqual(matches[0]['_odds_type'],'opening')

    def test_pinnacle_cutoff_excludes_potentially_stale_prices(self):
        matches,_=parse_historical_csv([csv_upload()],provider='PS')
        self.assertIsNone(matches[0]['_odds'])
        matches,_=parse_historical_csv([csv_upload(Date='22/07/2025')],provider='PS')
        self.assertEqual(matches[0]['_provider'],'PS')

    def test_average_is_explicit_separate_reference(self):
        matches,_=parse_historical_csv([csv_upload()],provider='Avg')
        self.assertEqual(matches[0]['_provider'],'Avg');self.assertEqual(matches[0]['_odds'],[2.1,3.4,3.9])

    def test_zip_only_imports_supported_divisions_without_extraction(self):
        data=io.BytesIO()
        with zipfile.ZipFile(data,'w') as z:
            z.writestr('E0.csv',csv_upload().getvalue());z.writestr('SC0.csv',b'unsupported')
        selected=expand_historical_files([upload('season.zip',data.getvalue())])
        self.assertEqual(len(selected),1);self.assertEqual(len(parse_historical_csv(selected)[0]),1)

    def test_path_traversal_zip_is_rejected(self):
        data=io.BytesIO()
        with zipfile.ZipFile(data,'w') as z:z.writestr('../E0.csv',csv_upload().getvalue())
        with self.assertRaises(ValueError):expand_historical_files([upload('bad.zip',data.getvalue())])

    def test_negative_goals_are_rejected(self):
        matches,rejected=parse_historical_csv([csv_upload(FTHG='-1')])
        self.assertEqual(matches,[]);self.assertEqual(rejected,1)

if __name__=='__main__':unittest.main()
