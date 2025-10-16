# features/generate_ts2vec_embeddings.py

def generate_ts2vec_features(time_series_df):
    '''
    Takes raw OHLCV DataFrame and returns TS2Vec embeddings per timestamp
    '''
    from ts2vec import TS2Vec
    encoder = TS2Vec(input_dims=time_series_df.shape[1])
    emb = encoder.fit_transform(time_series_df.values, n_epochs=20)
    return emb
