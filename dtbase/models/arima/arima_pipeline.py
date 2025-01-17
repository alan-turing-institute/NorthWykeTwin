import logging
from copy import deepcopy
from datetime import timedelta
from typing import Tuple, Union

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_percentage_error, mean_squared_error
from sklearn.model_selection import TimeSeriesSplit
from statsmodels.tsa.statespace.sarimax import SARIMAX, SARIMAXResultsWrapper

from dtbase.models.arima.config import ConfigArima

logger = logging.getLogger(__name__)


def get_forecast_timestamp(data: pd.Series, arima_config: ConfigArima) -> pd.Timestamp:
    """
    Return the end-of-forecast timestamp.

    Parameters:
        data: pandas Series containing a time series.
            Must be indexed by timestamp.
        arima_config: A ConfigArima object containing parameters for the model.

    Returns:
        forecast_timestamp: end-of-forecast timestamp,
            calculated by adding the `hours_forecast`
            parameter of config_arima.ini to the last timestamp
            of `data`.
    """
    if arima_config.hours_forecast <= 0:
        logger.error(
            "The 'hours_forecast' parameter in config_arima.ini must be greater than "
            "zero."
        )
        raise Exception
    end_of_sample_timestamp = data.index[-1]
    forecast_timestamp = end_of_sample_timestamp + timedelta(
        hours=arima_config.hours_forecast
    )
    return forecast_timestamp


def fit_arima(
    train_data: pd.Series, arima_config: ConfigArima
) -> SARIMAXResultsWrapper:
    """
    Fit a SARIMAX statsmodels model to a
    training dataset (time series).
    The model parameters are specified through the
    `arima_order`, `seasonal_order` and `trend`
    settings in config_arima.ini.

    Parameters:
        train_data: a pandas Series containing the
            training data on which to fit the model.
        arima_config: A ConfigArima object containing parameters for the model.

    Returns:
        model_fit: the fitted model, which can now be
            used for forecasting.
    """
    model = SARIMAX(
        train_data,
        order=arima_config.arima_order,
        seasonal_order=arima_config.seasonal_order,
        trend=arima_config.trend,
    )
    model_fit = model.fit(
        disp=False
    )  # fits the model by maximum likelihood via Kalman filter
    return model_fit


def forecast_arima(
    model_fit: SARIMAXResultsWrapper,
    forecast_timestamp: pd.Timestamp,
    arima_config: ConfigArima,
) -> Tuple[pd.Series, pd.DataFrame]:
    """
    Produce a forecast given a trained SARIMAX model.

    Arguments:
        model_fit: the SARIMAX model fitted to training data.
            This is the output of `fit_arima`.
        forecast_timestamp: the end-of-forecast timestamp.
        arima_config: A ConfigArima object containing parameters for the model.

    Returns:
        mean_forecast: the forecast mean. A pandas Series, indexed
            by timestamp.
        conf_int: the lower and upper bounds of the confidence
            intervals of the forecasts. A pandas Dataframe, indexed
            by timestamp. Specify the confidence level through parameter
            `alpha` in config_arima.ini.
    """
    alpha = arima_config.alpha
    forecast = model_fit.get_forecast(steps=forecast_timestamp).summary_frame(
        alpha=alpha
    )
    mean_forecast = forecast["mean"]  # forecast mean
    conf_int = forecast[
        ["mean_ci_lower", "mean_ci_upper"]
    ]  # get confidence intervals of forecasts
    return mean_forecast, conf_int


def construct_cross_validator(
    data: pd.Series, train_fraction: float = 0.8, n_splits: int = 4
) -> TimeSeriesSplit:
    """
    Construct a time series cross validator (TSCV) object.

    Arguments:
        data: time series for which to construct the TSCV,
            as a pandas Series.
        train_fraction: fraction of `data` to use as the
            initial model training set. The remaining data
            will be used as the testing set in cross-validation.
        n_splits: number of splits/folds of the testing set
            for cross-validation.
    Returns:
        tscv: the TSCV object, constructed with
            sklearn.TimeSeriesSplit.
    """
    if (train_fraction < 0.5) or (train_fraction >= 1):
        logger.error(
            "The fraction of training data for cross-validation must be >= 0.5 and < 1."
        )
        raise ValueError
    n_obs = len(data)  # total number of observations
    n_obs_test = n_obs * (
        1 - train_fraction
    )  # total number of observations used for testing
    test_size = int(
        n_obs_test // n_splits
    )  # number of test observations employed in each fold
    if test_size < 1:
        logger.error(
            "A valid cross-validator cannot be built. The size of the test set is less "
            "than 1."
        )
        raise Exception
    tscv = TimeSeriesSplit(
        n_splits=n_splits, test_size=test_size
    )  # construct the time series cross-validator
    return tscv


def cross_validate_arima(
    data: pd.Series,
    tscv: TimeSeriesSplit,
    arima_config: ConfigArima,
    refit: bool = False,
) -> dict:
    """
    Cross-validate a SARIMAX statsmodel model.

    Arguments:
        data: pandas Series containing the time series
            for which the SARIMAX model is built.
        tscv: the time series cross-validator object,
            returned by `construct_cross_validator`.
        arima_config: A ConfigArima object containing parameters for the model.
        refit: specify whether to refit the model
            parameters when new observations are added
            to the training set in successive cross-
            validation folds (True) or not (False).
            The default is False, as this is faster for
            large datasets.
    Returns:
        metrics: a dict containing two model metrics:
            "RMSE": the cross-validated root-mean-squared-error.
                See `sklearn.metrics.mean_squared_error`.
            "MAPE": the cross-validated mean-absolute-percentage-error.
                See `sklearn.metrics.mean_absolute_percentage_error`.
    """
    metrics = dict.fromkeys(["RMSE", "MAPE"])
    rmse = []  # this will hold the RMSE at each fold
    mape = []  # this will hold the MAPE score at each fold

    def update_result(
        model_fit: SARIMAXResultsWrapper, cv_test: pd.Series, test_index: pd.Series
    ) -> None:
        # compute the forecast for the test sample of the current fold
        forecast = model_fit.forecast(steps=len(test_index))
        # compute the RMSE for the current fold
        rmse.append(mean_squared_error(cv_test.values, forecast.values, squared=False))
        # compute the MAPE for the current fold
        mape.append(mean_absolute_percentage_error(cv_test.values, forecast.values))

    data_split = iter(tscv.split(data))
    # only force model fitting in the first fold
    train_index, test_index = next(data_split)
    cv_train, cv_test = data.iloc[train_index], data.iloc[test_index]
    model_fit = fit_arima(cv_train, arima_config)
    update_result(model_fit, cv_test, test_index)

    # loop through all folds
    for _, test_index in data_split:
        # in all other folds, the model is refitted only if requested by the user
        # here we append to the current train set the test set of the previous fold
        cv_test_old = deepcopy(cv_test)
        cv_test = data.iloc[test_index]
        if refit:
            model_fit = model_fit.append(cv_test_old, refit=True)
        else:
            # extend is faster than append with refit=False
            model_fit = model_fit.extend(cv_test_old)
        update_result(model_fit, cv_test, test_index)

    metrics["RMSE"] = np.mean(
        rmse
    )  # the cross-validated RMSE: the mean RMSE across all folds
    metrics["MAPE"] = np.mean(
        mape
    )  # the cross-validated MAPE: the mean MAPE across all folds
    return metrics


def arima_pipeline(
    data: pd.Series, arima_config: ConfigArima
) -> Tuple[pd.Series, pd.DataFrame, Union[dict, None]]:
    """
    Run the ARIMA model pipeline, using the SARIMAX model provided
    by the `statsmodels` library. This is the parent function of
    the `arima_pipeline` module.
    The SARIMAX model parameters can be specified via the
    `config_arima.ini` file.

    Arguments:
        data: the time series on which to train the SARIMAX model,
            as a pandas Series indexed by timestamp.
        arima_config: A ConfigArima object containing parameters for the model.
    Returns:
        mean_forecast: a pandas Series, indexed by timestamp,
            containing the forecast mean. The number of hours to
            forecast into the future can be specified through the
            `config_arima.ini` file.
        conf_int: a pandas Dataframe, indexed by timestamp, containing
            the lower an upper confidence intervals for the forecasts.
        metrics: a dictionary containing the cross-validated root-mean-
            squared-error (RMSE) and mean-absolute-percentage-error (MAPE)
            for the fitted SARIMAX model. If the user requests not to perform
            cross-validation through the `config_arima.ini` file, `metrics`
            is assigned `None`.
    """
    if not isinstance(data.index, pd.DatetimeIndex):
        logger.error(
            "The time series on which to train the ARIMA model must be indexed by "
            "timestamp."
        )
        raise ValueError
    if arima_config.arima_order != (4, 1, 2):
        logger.warning(
            "The 'arima_order' setting in config_arima.ini has been set to something "
            "different than (4, 1, 2)."
        )
    if arima_config.seasonal_order != (1, 1, 0, 24):
        logger.warning(
            "The 'seasonal_order' setting in config_arima.ini has been set to "
            "something different than (1, 1, 0, 24)."
        )
    if arima_config.hours_forecast != 48:
        logger.warning(
            "The 'hours_forecast' setting in config_arima.ini has been set to "
            "something different than 48."
        )
    # perform time series cross-validation if requested by the user
    cross_validation = arima_config.perform_cv
    if cross_validation:
        refit = arima_config.cv_refit
        if refit:
            logger.info("Running time series cross-validation WITH parameter refit...")
        else:
            logger.info(
                "Running time series cross-validation WITHOUT parameter refit..."
            )
        try:
            tscv = construct_cross_validator(data)
            try:
                metrics = cross_validate_arima(data, tscv, arima_config, refit=refit)
            # TODO This except clause should be more specific. What are the possible
            # errors we might expect from cross_validate_arima?
            except Exception:
                logger.warning(
                    "Could not perform cross-validation. "
                    "Continuing without ARIMA model testing."
                )
                metrics = None
            else:
                logger.info(
                    (
                        "Done running cross-validation. "
                        "The CV root-mean-squared-error is: {0:.2f}. "
                        "The CV mean-absolute-percentage-error is: {1:.3f}"
                    ).format(metrics["RMSE"], metrics["MAPE"])
                )
        # TODO This except clause should be more specific. What are the possible
        # errors we might expect from construct_cross_validator?
        except Exception:
            logger.warning(
                "Could not build a valid cross-validator. "
                "Continuing without ARIMA model testing."
            )
            metrics = None
    else:
        metrics = None
    # fit the model and compute the forecast
    logger.info("Fitting the model...")
    model_fit = fit_arima(data, arima_config)
    logger.info("Done fitting the model.")
    forecast_timestamp = get_forecast_timestamp(data, arima_config)
    logger.info("Computing forecast...")
    logger.info(
        "Start of forecast timestamp: {0}. End of forecast timestamp: {1}".format(
            data.index[-1], forecast_timestamp
        )
    )
    mean_forecast, conf_int = forecast_arima(
        model_fit, forecast_timestamp, arima_config
    )
    logger.info("Done forecasting.")

    return mean_forecast, conf_int, metrics
