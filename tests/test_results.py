from gx_tool_db.config import TestDataMergeStrategy
from gx_tool_db.models import TestResults
from gx_tool_db.results import result_collections
from ._data import DATA_DIRECTORY


def test_walking():
    found_a_collection = False
    for collection in result_collections(DATA_DIRECTORY):
        found_a_collection = True
        assert collection.uri.endswith(".json")
    assert found_a_collection


def test_test_data_merge():
    results1 = TestResults(__root__={
        0: {
            'job_create_time': '2021-06-29T04:29:32.110891',
            'status': 'success',
        },
        1: {
            'job_create_time': '2021-06-29T04:29:32.117016',
            'status': 'success',
        },
    })
    results2 = TestResults(__root__={
        0: {
            'status': 'success',
        },
        1: {
            'status': 'success',
        },
    })

    for strategy in TestDataMergeStrategy.__members__.values():
        merge21 = results2.merged(results1, strategy)
        assert merge21.__root__[0]
        assert merge21.__root__[1]
        assert merge21.__root__[0].job_create_time == '2021-06-29T04:29:32.110891'
        assert merge21.__root__[1].job_create_time == '2021-06-29T04:29:32.117016'

        merge12 = results1.merged(results2, strategy)
        if strategy in [TestDataMergeStrategy.latest_added, TestDataMergeStrategy.latest_added_indexwise]:
            assert merge12.__root__[0]
            assert merge12.__root__[1]
            assert merge12.__root__[0].job_create_time is None
            assert merge12.__root__[1].job_create_time is None
        else:
            assert merge12.__root__[0]
            assert merge12.__root__[1]
            assert merge12.__root__[0].job_create_time == '2021-06-29T04:29:32.110891'
            assert merge12.__root__[1].job_create_time == '2021-06-29T04:29:32.117016'

    # results1 but 1 month newer...
    results3 = TestResults(__root__={
        0: {
            'job_create_time': '2021-07-29T04:29:32.110891',
            'status': 'success',
        },
        1: {
            'job_create_time': '2021-07-29T04:29:32.117016',
            'status': 'success',
        },
    })

    for strategy in TestDataMergeStrategy.__members__.values():
        merge31 = results3.merged(results1, strategy)
        if strategy in [TestDataMergeStrategy.latest_added, TestDataMergeStrategy.latest_added_indexwise]:
            assert merge31.__root__[0].job_create_time == '2021-06-29T04:29:32.110891'
            assert merge31.__root__[1].job_create_time == '2021-06-29T04:29:32.117016'
        elif strategy in [TestDataMergeStrategy.latest_executed, TestDataMergeStrategy.latest_executed_indexwise]:
            assert merge31.__root__[0].job_create_time == '2021-07-29T04:29:32.110891'
            assert merge31.__root__[1].job_create_time == '2021-07-29T04:29:32.117016'

        merge13 = results1.merged(results3, strategy)
        assert merge13.__root__[0].job_create_time == '2021-07-29T04:29:32.110891'
        assert merge13.__root__[1].job_create_time == '2021-07-29T04:29:32.117016'

    # 4 and 5 each have one failure and one success but on alternative indices, should merge into two success under best_indexwise...
    results4 = TestResults(__root__={
        0: {
            'job_create_time': '2021-06-29T04:29:32.110891',
            'status': 'failed',
        },
        1: {
            'job_create_time': '2021-06-29T04:29:32.117016',
            'status': 'success',
        },
    })
    results5 = TestResults(__root__={
        0: {
            'job_create_time': '2021-06-29T04:29:32.110891',
            'status': 'success',
        },
        1: {
            'job_create_time': '2021-06-29T04:29:32.117016',
            'status': 'failed',
        },
    })
    for strategy in TestDataMergeStrategy.__members__.values():
        merge45 = results4.merged(results5, strategy)
        merge54 = results5.merged(results4, strategy)
        if strategy in [TestDataMergeStrategy.best_indexwise]:
            assert merge45.__root__[0].successful
            assert merge45.__root__[1].successful

            assert merge54.__root__[0].successful
            assert merge54.__root__[1].successful
    # A test result with the same number of passes but more tests executed is considered "better".
    results6 = TestResults(__root__={
        0: {
            'job_create_time': '2021-07-29T04:29:32.110891',
            'status': 'failed',
        },
        1: {
            'job_create_time': '2021-07-29T04:29:32.117016',
            'status': 'success',
        },
        2: {
            'job_create_time': '2021-07-29T04:29:33.110891',
            'status': 'failed',
        },
    })
    for strategy in TestDataMergeStrategy.__members__.values():
        merge46 = results4.merged(results6, strategy)
        merge64 = results6.merged(results4, strategy)
        if strategy in [TestDataMergeStrategy.best, TestDataMergeStrategy.best_indexwise]:
            assert len(merge64.__root__) == 3
            assert len(merge46.__root__) == 3
            assert merge46.__root__[0].job_create_time == '2021-07-29T04:29:32.110891'
            assert merge64.__root__[0].job_create_time == '2021-07-29T04:29:32.110891'
