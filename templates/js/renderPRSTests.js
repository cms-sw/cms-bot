function arrayIncludes(array, value){
  if (array.indexOf(value) >= 0) {
    return true;
  }
}
/**
 * creates a row with the information about a test result
 */
getResultRow = function( resultsDict , resultsKey ){

  var column1Label = LABELS[ resultsKey ]
  var column2Label = LABELS2[ resultsKey ]
  var linkURL = LOCATIONS[ resultsKey ]
 
  var testResult = resultsDict[ resultsKey ]
  hadErrors = testResult == 'ERROR'

  if ( testResult == null || testResult == 'NOTRUN' ){

     column2Label = 'Not Run'
     linkURL = '#' 

  }else if( testResult == 'QUEUED' ){

    column2Label = 'Queued'
    linkURL = '#'

  }else if( testResult == 'RUNNING' ){

    column2Label = 'Running'
    linkURL = '#'

  }else if( resultsKey == COMPARISON_KEY ){

    column2Label = 'See Comparison Results'
    linkURL = BASE_COMPARISONS_URL + resultsDict[ BASE_IB_KEY ] + '+' + resultsDict[ PR_NUMBER_KEY ] + '/' + testResult + '/' 

  }


  var row = $( '<tr>' )
  var cellColumn1 = $( '<td>' )
  cellColumn1.text( column1Label )
  row.append( cellColumn1 )


  var cellColumn2 = $( '<td>' )
  var linkTest = $( '<a>' )
  linkTest.attr( 'href' , linkURL )
  linkTest.text( column2Label )
  cellColumn2.append( linkTest )

  if ( hadErrors ){

    var errorsFoundSpan = $( '<span>' ).text( ' Errors Found' )
    var errorsGlyph = $( '<span>' ).attr( 'class' , 'glyphicon glyphicon-warning-sign' )
    cellColumn2.append( $( '<br>' ) )
    cellColumn2.append( errorsGlyph )
    cellColumn2.append( errorsFoundSpan )
    
  }

  row.append( cellColumn2 )

  return row
}

/**
 * Fills the results table
 */
fillResultsTable = function( resultsDict, table ){
  var valuex = {}
  for (k in LABELS){valuex[LABELS[k]]=k;}
  var values = Object.keys(valuex);
  values.sort();
  $.each (values, function(index, value){
    key = valuex[value];
    if (! arrayIncludes(IGNORE_KEYS, key)){
    var resultsRow = getResultRow( resultsDict , key )
    table.append( resultsRow )
    }
  })
}

/**
 * Returns link to the pull request in github
 */
getLinkToPR = function( pr ){

  var pr_num = pr.split("#")[1];
  var pr_repo = pr.split("#")[0];
  return 'https://github.com/'+ pr_repo + '/pull/' + pr_num;

}

/**
 * returns a link to the IB in the IB Pages
 */
// old version
//getLinkToIB = function( baseIB ){
//
//  return BASE_IB_URL + '#' + baseIB
//
//}

// point to new version
getLinkToIB = function( baseIB ){
  var reReleaseInfo = /^([a-zA-Z]+_[0-9]+_[0-9])+_(.*)_(\d{4}-\d{2}-\d{2}-\d{4})/;
  var releaseQueue = baseIB.match(reReleaseInfo)[1];
  return IB_PAGE_V2 + releaseQueue + '_X';
}

/**
 * returns the header for the summary page
 */
getHeader = function( resultsDict ){

  var header = $( '<span>' ).attr( 'align' , 'center' )
  var title = $( '<h2>' ).text( 'Tests Results:')

  var ibLink = $( "<a>" ).text( resultsDict[ BASE_IB_KEY ] )
  ibLink.attr( 'href' , getLinkToIB( resultsDict[ BASE_IB_KEY ] ) )

  var subtitle = $( '<h3>' )
  subtitle.append( ibLink );

    PRS = resultsDict[ PR_NUMBERS_KEY ].split(' ')
    $.each( PRS , function( index ){

      var pr = PRS[ index ]
      var addPrLink = $( "<a>" ).text( pr )
      addPrLink.attr( 'href' , getLinkToPR( pr ) )
      subtitle.append( $( '</br>' )).append( addPrLink )

    })



  header.append( title )
  header.append( subtitle )

  var baselineSubtitle = $( '<h5>' )
  header.append( baselineSubtitle )
  var baselineLink = $( "<a>" ).text( "See baseline used for the comparisons" )
  baselineSubtitle.append( baselineLink )
  baselineLink.attr( 'href' , '/SDT/jenkins-artifacts/ib-baseline-tests/' + resultsDict[ COMPARISON_IB_KEY ] )

  header.append( $( '<br>' ) )

  return header


}


//----------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------

/**
 * Parses the text of the results into a dictionary
 *
 */
parseResultsIntoDict = function( results ){

  var lines = results.split( '\n' )
  var dict = {}

  for ( index in lines ){

    var line = lines[ index ].trim()

    if( line && line !== '' ){
        var lineParts = line.split( ';' )
        var key = lineParts[0].trim()
        var vParts = lineParts[1].trim().split(',')
        dict[ key ] = vParts[0].trim()
        if (!(key in LABELS) && ! arrayIncludes(IGNORE_KEYS, key))
        {
          if (vParts.length > 1){LABELS[key] = vParts[1].trim()}
          else{LABELS[key] = key}
          if (vParts.length > 2){LABELS2[key] = vParts[2].trim()}
          else{LABELS2[key] = 'See Log'}
          if (vParts.length > 3){LOCATIONS[key] = vParts[3].trim()}
          else{LOCATIONS[key] = 'unknown.log'}
        }
    }

  }

  return dict

}

//----------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------
// Keys to ignore in testsResults.txt
IGNORE_KEYS=["PR_NUMBER", "PR_NUMBERS", "ADDITIONAL_PRS", "BASE_IB", "BUILD_NUMBER", "COMPARISON_IB"];
BASE_IB_KEY = 'BASE_IB';
PR_NUMBER_KEY = 'PR_NUMBER';
PR_NUMBERS_KEY = 'PR_NUMBERS';
BUILD_NUMBER_KEY = 'BUILD_NUMBER';
ADDITIONAL_PRS_KEY = 'ADDITIONAL_PRS';
CMSSWTOOLCONF_RESULTS_KEY = 'CMSSWTOOLCONF_RESULTS';
COMPILATION_RESULTS_KEY = 'COMPILATION_RESULTS';
BUILD_LOG_KEY = 'BUILD_LOG';
UNIT_TEST_RESULTS_KEY = 'UNIT_TEST_RESULTS';
MATRIX_TESTS_KEY = 'MATRIX_TESTS';
ADDON_TESTS_KEY = 'ADDON_TESTS';
IGPROF_KEY = 'IGPROF';
STATIC_CHECKS_KEY = 'STATIC_CHECKS';
COMPARISON_KEY = 'COMPARISON';
DQM_TESTS_KEY = 'DQM_TESTS';
CODE_RULES_TESTS_KEY = 'CODE_RULES';
DUPLICATE_DICT_RULES_KEY = 'DUPLICATE_DICT_RULES';
MATERIAL_BUDGET_TESTS_KEY = 'MATERIAL_BUDGET';
CLANG_COMPILATION_KEY = 'CLANG_COMPILATION_RESULTS';
BASE_IB_URL = '/SDT/html/showIB.html';
COMPARISON_IB_KEY = "COMPARISON_IB"
IB_PAGE_V2 = '/SDT/html/cmssdt-ib/#/ib/';

LABELS = {};
LABELS[CMSSWTOOLCONF_RESULTS_KEY] = 'Externals compilation';
LABELS[COMPILATION_RESULTS_KEY] = 'Compilation log';
LABELS[BUILD_LOG_KEY] = 'Compilation warnings summary';
LABELS[UNIT_TEST_RESULTS_KEY] = 'Unit Tests';
LABELS[MATRIX_TESTS_KEY] = 'Matrix Tests Outputs';
LABELS[ADDON_TESTS_KEY] = 'AddOn Tests Outputs';
LABELS[IGPROF_KEY] = 'Igprof for 25202';
LABELS[STATIC_CHECKS_KEY] = 'Static checks outputs';
LABELS[COMPARISON_KEY] = 'Comparison with the baseline';
LABELS[DQM_TESTS_KEY] = 'DQM Tests';
LABELS[CLANG_COMPILATION_KEY] = 'Clang Compilation';
LABELS[CODE_RULES_TESTS_KEY] = 'CMSSW Code Rules';
LABELS[DUPLICATE_DICT_RULES_KEY] = 'Duplicate Dictionaries';
LABELS[MATERIAL_BUDGET_TESTS_KEY] = 'Material budget';

LABELS2 = {};
LABELS2[CMSSWTOOLCONF_RESULTS_KEY] = 'See Log';
LABELS2[COMPILATION_RESULTS_KEY] = 'See Log';
LABELS2[BUILD_LOG_KEY] = 'See Log';
LABELS2[UNIT_TEST_RESULTS_KEY] = 'See Log';
LABELS2[MATRIX_TESTS_KEY] = 'See Logs';
LABELS2[ADDON_TESTS_KEY] = 'See Logs';
LABELS2[IGPROF_KEY] = 'See results';
LABELS2[STATIC_CHECKS_KEY] = 'See Static Checks';
LABELS2[COMPARISON_KEY] = 'See results';
LABELS2[DQM_TESTS_KEY] = 'See results';
LABELS2[CLANG_COMPILATION_KEY] = 'See Log';
LABELS2[CODE_RULES_TESTS_KEY] = 'See Log';
LABELS2[DUPLICATE_DICT_RULES_KEY] = 'See Log';
LABELS2[MATERIAL_BUDGET_TESTS_KEY] = 'See Log';

LOCATIONS = {};
LOCATIONS[CMSSWTOOLCONF_RESULTS_KEY] = 'cmsswtoolconf.log';
LOCATIONS[COMPILATION_RESULTS_KEY] = 'build.log';
LOCATIONS[BUILD_LOG_KEY] = 'build-logs';
LOCATIONS[UNIT_TEST_RESULTS_KEY] = 'unitTests.log';
LOCATIONS[MATRIX_TESTS_KEY] = 'runTheMatrix-results';
LOCATIONS[ADDON_TESTS_KEY] = 'addOnTests';
LOCATIONS[IGPROF_KEY] = 'igprof-results-data';
LOCATIONS[STATIC_CHECKS_KEY] = 'llvm-analysis';
LOCATIONS[COMPARISON_KEY] = 'See results';
LOCATIONS[DQM_TESTS_KEY] = 'DQMTestsResults';
LOCATIONS[CLANG_COMPILATION_KEY] = 'buildClang.log';
LOCATIONS[CODE_RULES_TESTS_KEY] = 'codeRules';
LOCATIONS[DUPLICATE_DICT_RULES_KEY] = 'dupDict';
LOCATIONS[MATERIAL_BUDGET_TESTS_KEY] = 'material-budget';

BASE_COMPARISONS_URL = '/SDT/@JENKINS_PREFIX@-artifacts/baseLineComparisons/';

