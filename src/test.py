import json
import os
import os.path
import itertools
import tempfile
import operator

import db
import recommendations
import main

import disco.ddfs

def cliqueness(build_name, dois):
    """Percentage of recommendations for this set which are not in this set"""
    scores = db.SingleValue(build_name, 'scores')

    dois = set(dois)
    inside = 0
    outside = 0
    for doi in dois:
        try:
            recommendations = scores.get(doi)
            for (score, recommendation) in recommendations:
                if recommendation in dois:
                    inside += 1
                else:
                    outside += 1
        except KeyError:
            # presumably we have no data for this doi
            pass
    return float(inside) / (inside+outside)

class RegressionError(Exception):
    pass

def regression(old_build_name, new_build_name):
    num_files = 0

    for db_name in ['scores', 'histograms']:
        old_db = db.SingleValue(old_build_name, db_name)
        new_db = db.SingleValue(new_build_name, db_name)

        num_keys = 0

        for ((old_key, old_value), (new_key, new_value)) in itertools.izip_longest(old_db, new_db, fillvalue=(None, None)):
            num_keys += 1
            if (new_key is None) or (old_key < new_key):
                print 'Key "%s" in db "%s" is present in old build and missing in new build' % (old_key, db_name)
                raise RegressionError()
            elif (old_key is None) or (old_key > new_key):
                print 'Key "%s" in db "%s" is present in new build and missing in old build' % (new_key, db_name)
                raise RegressionError()
            elif old_value != new_value:
                print 'Values do not match for key %s' % old_key
                print 'Old value:'
                print old_value
                print 'New value:'
                print new_value
                raise RegressionError()

        print 'Regression test passed for db %s (%i keys compared)' % (db_name, num_keys)

unit_data = {
    'A': [0, 8, 9],
    'B': [0, 6],
    'C': [0, 6, 7],
    'D': [0, 4, 7],
    'E': [0, 4, 7],
    'F': [0, 3, 4],
    'G': [0, 3, 5],
    'H': [2, 3, 10],
    'I': [2, 3, 12],
    'J': [2, 10, 11, 12],
    'K': [12],
    'L': [13],
    }

unit_results = {
    u'A': [[1**2.0/3/2, u'B'], [1**2.0/3/3, u'G'], [1**2.0/3/3, u'F'], [1**2.0/3/3, u'E'], [1**2.0/3/3, u'D']],
    u'B': [[2**2.0/2/3, u'C'], [1**2.0/2/3, u'G'], [1**2.0/2/3, u'F'], [1**2.0/2/3, u'E'], [1**2.0/2/3, u'D']],
    u'C': [[2**2.0/3/2, u'B'], [2**2.0/3/3, u'E'], [2**2.0/3/3, u'D'], [1**2.0/3/3, u'G'], [1**2.0/3/3, u'F']],
    u'D': [[3**2.0/3/3, u'E'], [2**2.0/3/3, u'F'], [2**2.0/3/3, u'C'], [1**2.0/3/2, u'B'], [1**2.0/3/3, u'G']],
    u'E': [[3**2.0/3/3, u'D'], [2**2.0/3/3, u'F'], [2**2.0/3/3, u'C'], [1**2.0/3/2, u'B'], [1**2.0/3/3, u'G']],
    u'F': [[2**2.0/3/3, u'G'], [2**2.0/3/3, u'E'], [2**2.0/3/3, u'D'], [1**2.0/3/2, u'B'], [1**2.0/3/3, u'I']],
    u'G': [[2**2.0/3/3, u'F'], [1**2.0/3/2, u'B'], [1**2.0/3/3, u'I'], [1**2.0/3/3, u'H'], [1**2.0/3/3, u'E']],
    u'H': [[2**2.0/3/3, u'I'], [2**2.0/3/4, u'J'], [1**2.0/3/3, u'G'], [1**2.0/3/3, u'F']],
    u'I': [[2**2.0/3/3, u'H'], [2**2.0/3/4, u'K'], [1**2.0/3/1, u'J'], [1**2.0/3/3, u'G'], [1**2.0/3/3, u'F']],
    u'J': [[2**2.0/4/3, u'I'], [2**2.0/4/3, u'H'], [1**2.0/4/1, u'K']],
    u'K': [[1**2.0/1/3, u'I'], [1**2.0/1/4, u'J']],
    u'L': [],
}

class UnitTestError(Exception):
    pass

def unit_input(build_name, data):
    log_format = '{ _id: ObjectId(\'foo\'), d: 20110101, doi: "%s", i: "0000-0000", s: 0, ip: "192.0.2.%s" }\n'
    logs = ((log_format % (doi, ip) for doi, ips in data.items() for ip in ips))

    _, name = tempfile.mkstemp()
    with open(name, 'w') as file:
        file.writelines(logs)

    tag = 'test:' + build_name
    ddfs = disco.ddfs.DDFS()
    ddfs.delete(tag)
    ddfs.chunk(tag, ['file://' + name])

    return tag

def unit_check_results(build_name, results):
    failed = False
    for doi in results:
        expected = results[doi]
        actual = mr.get_result(build_name, 'recommendations', doi)
        if actual != sorted(actual, key=operator.itemgetter(0), reverse=True): # must be sorted by score
            print 'Result is not sorted for doi', doi
            print actual
            print '-' * 40
            failed = True
        if actual != expected:
            print 'Results did not match on doi', doi
            print 'Expected:', expected
            print 'Actual:', actual
            print '-' * 40
            failed = True
    if failed:
        print 'Failed!'
    else:
        print 'Passed!'

def unit_base(build_name='unit-base'):
    mr.drop_results(build_name)
    db.drop(recommendations.db_name(build_name))
    main.build_all(input=[unit_input(build_name, unit_data)], build_name=build_name)
    unit_check_results(build_name, unit_results)

def unit_merge(build_name='unit-merge'):
    half_a = dict([(doi, ips[0::2]) for doi, ips in unit_data[0::2]] + [(doi, ips[1::2]) for doi, ips in unit_data[1::2]])
    half_b = dict([(doi, ips[1::2]) for doi, ips in unit_data[0::2]] + [(doi, ips[0::2]) for doi, ips in unit_data[1::2]])

    mr.drop_results(build_name)
    db.drop(recommendations.db_name(build_name))
    main.build_all(input=[unit_input(build_name, half_a)], build_name=build_name)
    main.build_all(input=[unit_input(build_name, half_b)], build_name=build_name)
    unit_check_results(build_name, unit_results)

# test symmetry
