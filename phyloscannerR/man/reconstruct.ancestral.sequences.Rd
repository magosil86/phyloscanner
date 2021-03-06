% Generated by roxygen2: do not edit by hand
% Please edit documentation in R/ancestral_reconstruction_methods.R
\name{reconstruct.ancestral.sequences}
\alias{reconstruct.ancestral.sequences}
\title{Reconstruct the ancestral sequence at every node of the tree}
\usage{
reconstruct.ancestral.sequences(ptree, verbose = F, default = F, ...)
}
\arguments{
\item{ptree}{A list of class \code{phyloscanner.tree} (usually an item in a list of class \code{phyloscanner.trees})}

\item{verbose}{Verbose output}

\item{default}{If TRUE, the reconstruction is done according to the default model used in RAxML to build trees for phyloscanner. The \code{...} below will be ignored.}

\item{...}{Further arguments to be passed to \code{pml} and \code{optim.pml}}
}
\value{
An alignment of the sequences at all nodes (in \code{DNAbin} format)
}
\description{
Reconstruct the ancestral sequence at every node of the tree
}
