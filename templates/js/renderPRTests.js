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

  }else if( resultsKey == COMPARISON_GPU_KEY ){

    column2Label = 'See GPU Comparison Results'
    linkURL = BASE_COMPARISONS_GPU_URL + resultsDict[ BASE_IB_KEY ] + '+' + resultsDict[ PR_NUMBER_KEY ] + '/' + testResult + '/'

  }else if( resultsKey == COMPARISON_HIGH_STATS ){

    column2Label = 'See High Stats Comparison Results'
    linkURL = BASE_COMPARISONS_HIGH_STATS_URL + resultsDict[ BASE_IB_KEY ] + '+' + resultsDict[ PR_NUMBER_KEY ] + '/' + testResult + '/'

  }else if( resultsKey == COMPARISON_NANO ){

    column2Label = 'See Nano Comparison Results'
    linkURL = BASE_COMPARISONS_NANO_URL + resultsDict[ BASE_IB_KEY ] + '+' + resultsDict[ PR_NUMBER_KEY ] + '/' + testResult + '/'

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
BASE_IB_KEY = 'BASE_IB';
PR_NUMBER_KEY = 'PR_NUMBER';
PR_NUMBERS_KEY = 'PR_NUMBERS';
COMPARISON_KEY = 'COMPARISON';
COMPARISON_GPU_KEY = 'COMPARISON_GPU';
COMPARISON_HIGH_STATS = 'COMPARISON_HIGH_STATS';
COMPARISON_NANO = 'COMPARISON_NANO';
BASE_IB_URL = '/SDT/html/showIB.html';
COMPARISON_IB_KEY = "COMPARISON_IB"
IB_PAGE_V2 = '/SDT/html/cmssdt-ib/#/ib/';
IGNORE_KEYS=[PR_NUMBER_KEY, PR_NUMBERS_KEY, "ADDITIONAL_PRS", BASE_IB_KEY, "BUILD_NUMBER", COMPARISON_IB_KEY];

LABELS = {};
LABELS2 = {};
LOCATIONS = {};

BASE_COMPARISONS_URL = '/SDT/@JENKINS_PREFIX@-artifacts/baseLineComparisons/';
BASE_COMPARISONS_GPU_URL = '/SDT/@JENKINS_PREFIX@-artifacts/baseLineComparisonsGPU/';
BASE_COMPARISONS_HIGH_STATS_URL = '/SDT/@JENKINS_PREFIX@-artifacts/baseLineComparisonsHIGH_STATS/'
BASE_COMPARISONS_NANO_URL = '/SDT/@JENKINS_PREFIX@-artifacts/baseLineComparisonsNANO/'

