/**
 * creates a row with the information about a test result
 */
getResultRow = function( resultsDict , resultsKey ){

  var column1Label = LABELS[ resultsKey ]
  var column2Label = LABELS2[ resultsKey ]
  var linkURL = BASE_RESULTS_URL + 'PR-' + resultsDict[ PR_NUMBER_KEY ] + '/' + resultsDict[ BUILD_NUMBER_KEY ] + '/'+LOCATIONS[ resultsKey ]
 
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

  $.each( LABELS , function( key, value ){
    var resultsRow = getResultRow( resultsDict , key )
    table.append( resultsRow )

  })
  


}

/**
 * Returns link to the pull request in github
 */
getLinkToPR = function( prNumber ){

  return BASE_PR_URL + prNumber

}

/**
 * returns a link to the IB in the IB Pages
 */
getLinkToIB = function( baseIB ){

  return BASE_IB_URL + '#' + baseIB

}

/**
 * returns the header for the summary page
 */
getHeader = function( resultsDict ){

  var header = $( '<span>' ).attr( 'align' , 'center' )
  var title = $( '<h2>' ).text( 'Tests Results:')

  var ibLink = $( "<a>" ).text( resultsDict[ BASE_IB_KEY ] )
  ibLink.attr( 'href' , getLinkToIB( resultsDict[ BASE_IB_KEY ] ) )
  var prLink = $( "<a>" ).text( resultsDict[ PR_NUMBER_KEY ] )
  prLink.attr( 'href' , getLinkToPR( resultsDict[ PR_NUMBER_KEY ] ) )

  var subtitle = $( '<h3>' )
  subtitle.append( ibLink ).append( $( '<span>' ).text( ' + ' ) ).append( prLink ) 

  var adittionalPRS = resultsDict[ ADDITIONAL_PRS_KEY ]
  if ( adittionalPRS != '' ){
  
    addPRParts = adittionalPRS.split( ',' )
    $.each( addPRParts , function( index ){
      
      var pr = addPRParts[ index ]
      var addPrLink = $( "<a>" ).text( pr )
      addPrLink.attr( 'href' , getLinkToPR( pr ) )
      subtitle.append( $( '<span>' ).text( ', ' ) ).append( addPrLink )
  
    })

  }
  

  header.append( title )
  header.append( subtitle )
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

    var line = lines[ index ] 

    if( line != '' ){  
        var lineParts = line.split( ';' )
        dict[ lineParts[ 0 ] ] = lineParts[ 1 ]

    }

  }

  return dict

}

//----------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------

BASE_IB_KEY = 'BASE_IB'
PR_NUMBER_KEY = 'PR_NUMBER'
BUILD_NUMBER_KEY = 'BUILD_NUMBER'
ADDITIONAL_PRS_KEY = 'ADDITIONAL_PRS'
COMPILATION_RESULTS_KEY = 'COMPILATION_RESULTS'
UNIT_TEST_RESULTS_KEY = 'UNIT_TEST_RESULTS'
MATRIX_TESTS_KEY = 'MATRIX_TESTS'
IGPROF_KEY = 'IGPROF'
STATIC_CHECKS_KEY = 'STATIC_CHECKS'
COMPARISON_KEY = 'COMPARISON'
DQM_TESTS_KEY = 'DQM_TESTS'
CLANG_COMPILATION_KEY = 'CLANG_COMPILATION_RESULTS'
BASE_IB_URL = 'https://cmssdt.cern.ch/SDT/html/showIB.html'
BASE_PR_URL = 'https://github.com/cms-sw/cmssw/pull/'
BASE_RESULTS_URL = 'https://cmssdt.cern.ch/SDT/jenkins-artifacts/pull-request-integration/'

LABELS = {}
LABELS[ COMPILATION_RESULTS_KEY ] = 'Compilation'
LABELS[ UNIT_TEST_RESULTS_KEY ] = 'Unit Tests'
LABELS[ MATRIX_TESTS_KEY ] = 'Matrix Tests Outputs'
LABELS[ IGPROF_KEY ] = 'Igprof for 25202'
LABELS[ STATIC_CHECKS_KEY ] = 'Static checks outputs'
LABELS[ COMPARISON_KEY ] = 'Comparison with the baseline' 
LABELS[ DQM_TESTS_KEY ] = 'DQM Tests' 
LABELS[ CLANG_COMPILATION_KEY ] = 'Clang Compilation'

LABELS2 = {}
LABELS2[ COMPILATION_RESULTS_KEY ] = 'See Log'
LABELS2[ UNIT_TEST_RESULTS_KEY ] = 'See Log'
LABELS2[ MATRIX_TESTS_KEY ] = 'See Logs'
LABELS2[ IGPROF_KEY ] = 'See results'
LABELS2[ STATIC_CHECKS_KEY ] = 'See Static Checks'
LABELS2[ COMPARISON_KEY ] = 'See results'
LABELS2[ DQM_TESTS_KEY ] = 'See results'
LABELS2[ CLANG_COMPILATION_KEY ] = 'See Log'

LOCATIONS = {}
LOCATIONS[ COMPILATION_RESULTS_KEY ] = 'build.log'
LOCATIONS[ UNIT_TEST_RESULTS_KEY ] = 'unitTests.log'
LOCATIONS[ MATRIX_TESTS_KEY ] = 'runTheMatrix-results'
LOCATIONS[ IGPROF_KEY ] = 'igprof-results-data'
LOCATIONS[ STATIC_CHECKS_KEY ] = 'llvm-analysis'
LOCATIONS[ COMPARISON_KEY ] = 'See results'
LOCATIONS[ DQM_TESTS_KEY ] = 'DQMTestsResults'
LOCATIONS[ CLANG_COMPILATION_KEY ] = 'buildClang.log'

BASE_COMPARISONS_URL = 'https://cmssdt.cern.ch/SDT/jenkins-artifacts/baseLineComparisons/'
